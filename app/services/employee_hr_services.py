"""Pointage et salaires des employés."""
from app.core import validators as V
from app.core.exceptions import ValidationError
from app.repositories.repos import AttendanceRepository, SalaryRepository
from app.services.base import CrudService


class AttendanceService(CrudService):
    entity = "employee_attendance"
    repo_cls = AttendanceRepository
    read_perm, write_perm, delete_perm = "attendance.read", "attendance.write", "attendance.delete"
    default_desc = True

    def validate(self, data):
        status = V.choice(data, "status", "Statut", ("present", "absent", "late"))
        arrival = V.text(data, "arrival_time", "Heure d'arrivée", required=False, max_len=8)
        departure = V.text(data, "departure_time", "Heure de départ", required=False, max_len=8)
        if status == "absent":
            arrival = departure = None
        else:
            if not arrival or not departure:
                raise ValidationError("Heure d'arrivée et de départ obligatoires si présent ou en retard.")
            if arrival >= departure:
                raise ValidationError("L'heure d'arrivée doit être antérieure à l'heure de départ.")
        return {
            "employee_id": V.integer(data, "employee_id", "Employé", minimum=1),
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
        return {
            "employee_id": V.integer(data, "employee_id", "Employé", minimum=1),
            "monthly_amount": V.integer(data, "monthly_amount", "Salaire mensuel", minimum=1, maximum=50_000_000),
        }

    def update(self, id_, data) -> None:
        super().update(id_, data)
        self.db.execute(
            "UPDATE employee_salaries SET updated_at = datetime('now') WHERE id = ?", (id_,))
