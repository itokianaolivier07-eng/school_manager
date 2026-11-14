"""Pointage et salaires des employés."""
from datetime import date

from app.core import validators as V
from app.core.exceptions import NotFoundError, ValidationError
from app.repositories.repos import (AttendanceRepository, SalaryDisbursementRepository,
                                    SalaryRepository)
from app.services.base import CrudService


def pay_type_for_position(position):
    return "hourly" if "prof" in (position or "").casefold() else "monthly"


class AttendanceService(CrudService):
    entity = "employee_attendance"
    repo_cls = AttendanceRepository
    read_perm, write_perm, delete_perm = "attendance.read", "attendance.write", "attendance.delete"
    default_desc = True

    def validate(self, data):
        status = V.choice(data, "status", "Statut", ("present", "absent", "late"))
        arrival = V.time_hhmm(data, "arrival_time", "Heure d'arrivée")
        departure = V.time_hhmm(data, "departure_time", "Heure de départ")
        if status == "absent":
            arrival = departure = None
        else:
            if not arrival or not departure:
                raise ValidationError("Heure d'arrivée et de départ obligatoires si présent ou en retard.")
            if arrival >= departure:
                raise ValidationError("L'heure d'arrivée doit être antérieure à l'heure de départ.")
        return {
            "employee_id": V.integer(data, "employee_id", "Employé", required=True, minimum=1),
            "attendance_date": V.date_iso(data, "attendance_date", "Date de pointage"),
            "status": status,
            "arrival_time": arrival,
            "departure_time": departure,
            "comment": V.text(data, "comment", "Commentaire", required=False, max_len=200),
        }


class SalaryService(CrudService):
    entity = "employee_salaries"
    repo_cls = SalaryRepository
    read_perm, write_perm, delete_perm = "salaries.read", "salaries.write", "salaries.delete"

    def validate(self, data):
        employee_id = V.integer(data, "employee_id", "Employé", required=True, minimum=1)
        employee = self.db.one("SELECT position FROM teachers WHERE id = ?", (employee_id,))
        if employee is None:
            raise ValidationError("Employé introuvable.")
        pay_type = pay_type_for_position(employee["position"])
        monthly_amount = 0
        hourly_rate = 0
        if pay_type == "monthly":
            monthly_amount = V.integer(
                data, "monthly_amount", "Salaire mensuel", required=True,
                minimum=1, maximum=50_000_000)
        else:
            hourly_rate = V.integer(
                data, "hourly_rate", "Indemnité horaire", required=True,
                minimum=1, maximum=50_000_000)
        return {
            "employee_id": employee_id,
            "pay_type": pay_type,
            "monthly_amount": monthly_amount,
            "hourly_rate": hourly_rate,
        }

    def recommended_pay_type(self, employee_id):
        self.ctx.session.require(self.read_perm)
        employee = self.db.one("SELECT position FROM teachers WHERE id = ?", (int(employee_id),))
        if employee is None:
            raise ValidationError("Employé introuvable.")
        return pay_type_for_position(employee["position"])

    def update(self, id_, data) -> None:
        super().update(id_, data)
        self.db.execute(
            "UPDATE employee_salaries SET updated_at = datetime('now') WHERE id = ?", (id_,))

    def compensation(self, employee_id):
        self.ctx.session.require(self.read_perm)
        row = self.db.one(
            "SELECT s.employee_id, s.monthly_amount, s.hourly_rate, "
            "t.employee_no, t.first_name, t.last_name, t.position "
            "FROM employee_salaries s JOIN teachers t ON t.id = s.employee_id "
            "WHERE s.employee_id = ?", (int(employee_id),))
        if row is None:
            raise NotFoundError("Aucune rémunération de base définie pour cet employé.")
        result = dict(row)
        result["pay_type"] = pay_type_for_position(result["position"])
        return result

    def compensation_options(self):
        self.ctx.session.require(self.read_perm)
        rows = [dict(row) for row in self.db.all(
            "SELECT s.employee_id, t.employee_no, t.first_name, t.last_name, t.position, "
            "s.monthly_amount, s.hourly_rate "
            "FROM employee_salaries s JOIN teachers t ON t.id = s.employee_id "
            "ORDER BY t.last_name, t.first_name")]
        for row in rows:
            row["pay_type"] = pay_type_for_position(row["position"])
        return rows


class SalaryDisbursementService(CrudService):
    entity = "salary_disbursements"
    repo_cls = SalaryDisbursementRepository
    read_perm = "salaries.read"
    write_perm = "salaries.write"
    delete_perm = "salaries.delete"
    default_desc = True

    TITLES = ("Salaire", "Avance", "Indemnité horaire", "Autre")

    def validate(self, data):
        raise ValidationError("Utilisez record() pour enregistrer une sortie de salaire.")

    def create(self, data):
        return self.record(data)

    def update(self, id_, data):
        raise ValidationError("Une sortie de salaire enregistrée ne peut pas être modifiée.")

    def delete(self, id_):
        raise ValidationError("Une sortie de salaire enregistrée ne peut pas être supprimée.")

    def record(self, data):
        user = self.ctx.session.require(self.write_perm)
        employee_id = V.integer(data, "employee_id", "Employé", required=True, minimum=1)
        title = V.choice(data, "title", "Titre", self.TITLES)
        payout_date = V.date_iso(data, "payout_date", "Date de sortie")
        compensation = self.db.one(
            "SELECT s.monthly_amount, s.hourly_rate, t.position "
            "FROM employee_salaries s JOIN teachers t ON t.id = s.employee_id "
            "WHERE s.employee_id = ?", (employee_id,))
        if compensation is None:
            raise ValidationError("Aucune rémunération de base définie pour cet employé.")

        hours = hourly_rate = None
        if pay_type_for_position(compensation["position"]) == "hourly":
            hours = V.number(data, "hours", "Nombre d'heures", minimum=0.01, maximum=1000)
            hourly_rate = compensation["hourly_rate"]
            amount = round(hours * hourly_rate)
            if amount < 1:
                raise ValidationError("Le montant calculé doit être supérieur à zéro.")
        else:
            amount = V.integer(data, "amount", "Montant de la sortie", required=True,
                               minimum=1, maximum=50_000_000)

        school_year = school_year_for_date(payout_date)
        with self.db.transaction():
            payout_id = self.repo.insert({
                "employee_id": employee_id, "title": title, "payout_date": payout_date,
                "school_year": school_year, "hours": hours, "hourly_rate": hourly_rate,
                "amount": amount, "created_by": user.id,
            })
        return payout_id


def school_year_for_date(value):
    parsed = date.fromisoformat(value)
    start = parsed.year if parsed.month >= 9 else parsed.year - 1
    return f"{start}-{start + 1}"
