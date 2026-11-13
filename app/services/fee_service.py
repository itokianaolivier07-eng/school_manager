"""Écolages : tarifs par niveau, encaissements, reçus, annulations, impayés."""
from datetime import date

from app.core import school
from app.core import validators as V
from app.core.exceptions import NotFoundError, ValidationError
from app.repositories.finance_repos import PaymentRepository, TuitionFeeRepository
from app.services.base import CrudService


class FeeService(CrudService):
    entity = "tuition_fees"
    repo_cls = TuitionFeeRepository
    read_perm, write_perm, delete_perm = "fees.read", "fees.write", "fees.delete"

    def validate(self, data):
        return {
            "level": V.choice(data, "level", "Niveau", school.LEVELS),
            "school_year": V.school_year(data, "school_year"),
            "monthly_amount": V.integer(data, "monthly_amount", "Écolage mensuel", required=True,
                                        minimum=0, maximum=school.MAX_AMOUNT),
            "registration_fee": V.integer(data, "registration_fee", "Frais d'inscription",
                                          minimum=0, maximum=school.MAX_AMOUNT) or 0,
        }


class PaymentService(CrudService):
    """Lecture/liste via CrudService ; l'écriture passe uniquement par record() et cancel()."""
    entity = "payments"
    repo_cls = PaymentRepository
    read_perm = "payments.read"
    default_desc = True

    def create(self, data):
        raise ValidationError("Utilisez record() pour encaisser.")

    def update(self, id_, data):
        raise ValidationError("Un paiement ne se modifie pas : annulez-le puis ressaisissez-le.")

    def delete(self, id_):
        raise ValidationError("Un paiement ne se supprime pas : annulez-le.")

    # --- situation d'un élève ---
    def statement(self, student_id):
        self.ctx.session.require("payments.read")
        st = self.db.one(
            "SELECT s.id, s.matricule, s.last_name, s.first_name, s.tuition_discount, s.class_id, "
            "c.name AS class_name, c.level, c.school_year FROM students s "
            "LEFT JOIN classes c ON c.id = s.class_id WHERE s.id = ?", (int(student_id),))
        if st is None:
            raise NotFoundError("Élève introuvable.")
        if st["class_id"] is None:
            raise ValidationError("Cet élève n'a pas de classe : impossible de calculer l'écolage.")
        fee = self.db.one("SELECT * FROM tuition_fees WHERE level = ? AND school_year = ?",
                          (st["level"], st["school_year"]))
        if fee is None:
            raise ValidationError(f"Aucun tarif défini pour {st['level']} {st['school_year']} "
                                  "(onglet Tarifs).")
        paid = {(r["kind"], r["month"]): r["total"] for r in self.db.all(
            "SELECT kind, month, SUM(amount) AS total FROM payments WHERE student_id = ? "
            "AND school_year = ? AND cancelled = 0 GROUP BY kind, month",
            (st["id"], st["school_year"]))}
        monthly = school.net_monthly(fee["monthly_amount"], st["tuition_discount"])
        lines = [("registration", None, "Inscription", fee["registration_fee"])] + [
            ("monthly", m, school.MONTH_NAMES[m], monthly) for m in school.SCHOOL_MONTHS]
        rows = []
        for kind, month, label, due in lines:
            got = paid.get((kind, month), 0)
            balance = max(0, due - got)
            status = ("Gratuit" if due == 0 else "Payé" if balance == 0 else "Partiel" if got else "Impayé")
            rows.append({"kind": kind, "month": month, "label": label, "due": due, "paid": got,
                         "balance": balance, "status": status})
        return {"student": dict(st), "rows": rows, "total_due": sum(r["due"] for r in rows),
                "total_paid": sum(r["paid"] for r in rows)}

    # --- encaissement ---
    def record(self, student_id, data):
        user = self.ctx.session.require("payments.write")
        kind = V.choice(data, "kind", "Type", tuple(school.KINDS))
        month = None
        if kind == "monthly":
            month = V.integer(data, "month", "Mois", required=True)
            if month not in school.SCHOOL_MONTHS:
                raise ValidationError("Mois hors année scolaire (octobre à juin).")
        amount = V.integer(data, "amount", "Montant", required=True, minimum=1, maximum=school.MAX_AMOUNT)
        method = V.choice(data, "method", "Mode de paiement", tuple(school.METHODS))
        reference = V.text(data, "reference", "Référence", required=False, max_len=60)
        with self.db.transaction():
            st = self.statement(student_id)
            row = next(r for r in st["rows"] if r["kind"] == kind and r["month"] == month)
            if row["due"] == 0:
                raise ValidationError("Rien à payer pour cette période.")
            if amount > row["balance"]:
                raise ValidationError(f"Montant supérieur au reste à payer ({school.fmt_ar(row['balance'])}).")
            year = st["student"]["school_year"]
            pid = self.repo.insert({"student_id": st["student"]["id"], "school_year": year, "kind": kind,
                                    "month": month, "amount": amount, "method": method,
                                    "reference": reference, "received_by": user.id})
            receipt = f"R{year[:4]}-{pid:06d}"
            self.db.execute("UPDATE payments SET receipt_no = ? WHERE id = ?", (receipt, pid))
            self.log("payment", pid, f"{receipt} élève={student_id} {kind} mois={month} montant={amount}")
        return pid, receipt

    def cancel(self, payment_id, reason):
        user = self.ctx.session.require("payments.cancel")
        reason = V.text({"r": reason}, "r", "Motif d'annulation", max_len=200)
        if len(reason) < 3:
            raise ValidationError("Motif d'annulation trop court.")
        with self.db.transaction():
            row = self.db.one("SELECT cancelled FROM payments WHERE id = ?", (int(payment_id),))
            if row is None:
                raise NotFoundError("Paiement introuvable.")
            if row["cancelled"]:
                raise ValidationError("Ce paiement est déjà annulé.")
            self.db.execute("UPDATE payments SET cancelled = 1, cancel_reason = ? WHERE id = ?",
                            (reason, int(payment_id)))
            self.log("payment_cancel", int(payment_id), reason)

    def receipt_data(self, payment_id):
        self.ctx.session.require("payments.read")
        r = self.db.one(
            "SELECT p.*, s.matricule, s.last_name, s.first_name, c.name AS class_name, "
            "u.full_name AS cashier FROM payments p JOIN students s ON s.id = p.student_id "
            "LEFT JOIN classes c ON c.id = s.class_id LEFT JOIN users u ON u.id = p.received_by "
            "WHERE p.id = ?", (int(payment_id),))
        if r is None:
            raise NotFoundError("Paiement introuvable.")
        return dict(r)

    # --- impayés d'une classe ---
    def arrears(self, class_id, today=None):
        self.ctx.session.require("payments.read")
        today = today or date.today()
        elapsed = school.months_elapsed(today)
        current_start = int(school.current_school_year(today)[:4])
        rows = self.db.all(
            "SELECT s.id, s.matricule, s.last_name, s.first_name, s.tuition_discount, "
            "f.monthly_amount, f.registration_fee, c.school_year, "
            "COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.student_id = s.id "
            "AND p.school_year = c.school_year AND p.cancelled = 0), 0) AS paid "
            "FROM students s JOIN classes c ON c.id = s.class_id "
            "JOIN tuition_fees f ON f.level = c.level AND f.school_year = c.school_year "
            "WHERE s.class_id = ? AND s.status = 'active'", (int(class_id),))
        out = []
        for r in rows:
            class_start = int(r["school_year"][:4])
            if class_start < current_start:
                months_due = 9
            elif class_start > current_start:
                months_due = 0
            else:
                months_due = elapsed
            due = r["registration_fee"] + months_due * school.net_monthly(
                r["monthly_amount"], r["tuition_discount"])
            if due > r["paid"]:
                out.append({"id": r["id"], "matricule": r["matricule"], "last_name": r["last_name"],
                            "first_name": r["first_name"], "due": due, "paid": r["paid"],
                            "balance": due - r["paid"]})
        return sorted(out, key=lambda x: -x["balance"])
