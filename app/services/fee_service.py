"""Écolages : tarifs par niveau, encaissements, reçus, annulations, impayés."""
from datetime import date

from app.core import school
from app.core import validators as V
from app.core.exceptions import NotFoundError, ValidationError
from app.repositories.finance_repos import PaymentRepository, TuitionFeeRepository
from app.services.base import CrudService


class FeeService(CrudService):
    entity = "class_tuition_fees"
    repo_cls = TuitionFeeRepository
    read_perm, write_perm, delete_perm = "fees.read", "fees.write", "fees.delete"

    def validate(self, data):
        class_id = V.integer(data, "class_id", "Classe", required=True, minimum=1)
        school_class = self.db.one("SELECT school_year FROM classes WHERE id = ?", (class_id,))
        if school_class is None:
            raise ValidationError("Classe introuvable.")
        clean = {
            "class_id": class_id,
            "school_year": school_class["school_year"],
            "monthly_amount": V.integer(data, "monthly_amount", "Écolage mensuel", required=True,
                                        minimum=0, maximum=school.MAX_AMOUNT),
        }
        for field in school.FEE_AMOUNT_FIELDS.values():
            clean[field] = V.integer(data, field, "Montant", minimum=0,
                                     maximum=school.MAX_AMOUNT) or 0
        return clean

    def class_options(self):
        self.ctx.session.require(self.read_perm)
        return [(r["label"], r["id"]) for r in self.db.all(
            "SELECT id, name || ' — ' || school_year AS label FROM classes ORDER BY name")]


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
            "c.name AS class_name, c.school_year FROM students s "
            "LEFT JOIN classes c ON c.id = s.class_id WHERE s.id = ?", (int(student_id),))
        if st is None:
            raise NotFoundError("Élève introuvable.")
        if st["class_id"] is None:
            raise ValidationError("Cet élève n'a pas de classe : impossible de calculer l'écolage.")
        fee = self.db.one("SELECT * FROM class_tuition_fees WHERE class_id = ? AND school_year = ?",
                          (st["class_id"], st["school_year"]))
        if fee is None:
            raise ValidationError(f"Aucun tarif défini pour la classe {st['class_name']} "
                                  "{st['school_year']} (onglet Tarifs).")
        paid = {r["fee_code"]: r["total"] for r in self.db.all(
            "SELECT fee_code, SUM(amount) AS total FROM payments WHERE student_id = ? "
            "AND school_year = ? AND cancelled = 0 GROUP BY fee_code",
            (st["id"], st["school_year"]))}
        monthly = school.net_monthly(fee["monthly_amount"], st["tuition_discount"])
        rows = []
        for fee_code in school.FEE_ITEM_CODES:
            month = school.MONTHS_BY_FEE_CODE.get(fee_code)
            kind = "monthly" if month is not None else "registration"
            due = monthly if month is not None else fee[school.FEE_AMOUNT_FIELDS[fee_code]]
            got = paid.get(fee_code, 0)
            balance = max(0, due - got)
            status = ("Gratuit" if due == 0 else "Payé" if balance == 0 else "Partiel" if got else "Impayé")
            rows.append({"kind": kind, "month": month, "fee_code": fee_code,
                         "label": school.FEE_ITEM_LABELS[fee_code], "due": due, "paid": got,
                         "balance": balance, "status": status})
        return {"student": dict(st), "rows": rows, "total_due": sum(r["due"] for r in rows),
                "total_paid": sum(r["paid"] for r in rows)}

    # --- encaissement ---
    def record(self, student_id, data):
        user = self.ctx.session.require("payments.write")
        if "fee_code" in data:
            fee_code = V.choice(data, "fee_code", "Poste", school.FEE_ITEM_CODES)
        else:
            kind = V.choice(data, "kind", "Type", tuple(school.KINDS))
            if kind == "registration":
                fee_code = "droit"
            else:
                month = V.integer(data, "month", "Mois", required=True)
                fee_code = school.MONTH_FEE_CODES.get(month)
                if fee_code is None:
                    raise ValidationError("Mois hors année scolaire (septembre à juin).")
        month = school.MONTHS_BY_FEE_CODE.get(fee_code)
        kind = "monthly" if month is not None else "registration"
        amount = V.integer(data, "amount", "Montant", required=True, minimum=1, maximum=school.MAX_AMOUNT)
        method = V.choice(data, "method", "Mode de paiement", tuple(school.METHODS))
        reference = V.text(data, "reference", "Référence", required=False, max_len=60)
        with self.db.transaction():
            st = self.statement(student_id)
            row = next(r for r in st["rows"] if r["fee_code"] == fee_code)
            if row["due"] == 0:
                raise ValidationError("Rien à payer pour cette période.")
            if amount > row["balance"]:
                raise ValidationError(
                    f"Montant supérieur au reste à payer pour {row['label']} "
                    f"({school.fmt_ar(row['balance'])}).")
            year = st["student"]["school_year"]
            pid = self.repo.insert({"student_id": st["student"]["id"], "school_year": year, "kind": kind,
                                    "month": month, "fee_code": fee_code, "amount": amount, "method": method,
                                    "reference": reference, "received_by": user.id})
            receipt = f"R{year[:4]}-{pid:06d}"
            self.db.execute("UPDATE payments SET receipt_no = ? WHERE id = ?", (receipt, pid))
            self.log("payment", pid, f"{receipt} élève={student_id} poste={fee_code} montant={amount}")
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
            "f.monthly_amount, f.droit_amount + f.photocopy_amount + f.uniform_amount + "
            "f.activity_1_amount + f.activity_2_amount + f.activity_3_amount + "
            "f.activity_4_amount + f.activity_5_amount AS fixed_due, c.school_year, "
            "COALESCE((SELECT SUM(p.amount) FROM payments p WHERE p.student_id = s.id "
            "AND p.school_year = c.school_year AND p.cancelled = 0), 0) AS paid "
            "FROM students s JOIN classes c ON c.id = s.class_id "
            "JOIN class_tuition_fees f ON f.class_id = c.id AND f.school_year = c.school_year "
            "WHERE s.class_id = ? AND s.status = 'active'", (int(class_id),))
        out = []
        for r in rows:
            class_start = int(r["school_year"][:4])
            if class_start < current_start:
                months_due = len(school.SCHOOL_MONTHS)
            elif class_start > current_start:
                months_due = 0
            else:
                months_due = elapsed
            due = r["fixed_due"] + months_due * school.net_monthly(
                r["monthly_amount"], r["tuition_discount"])
            if due > r["paid"]:
                out.append({"id": r["id"], "matricule": r["matricule"], "last_name": r["last_name"],
                            "first_name": r["first_name"], "due": due, "paid": r["paid"],
                            "balance": due - r["paid"]})
        return sorted(out, key=lambda x: -x["balance"])
