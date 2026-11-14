"""Écolages : tarifs par niveau, encaissements, reçus, annulations, impayés."""
import csv
import os
from datetime import date

from app import config
from app.core import school
from app.core import validators as V
from app.core.exceptions import NotFoundError, ValidationError
from app.repositories.finance_repos import PaymentRepository, TuitionFeeRepository
from app.services.base import CrudService, Page
from app.services.student_service import csv_safe


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

    def history_filter_options(self):
        self.ctx.session.require(self.read_perm)
        years = [r["school_year"] for r in self.db.all(
            "SELECT DISTINCT school_year FROM payments ORDER BY school_year DESC")]
        classes = [dict(r) for r in self.db.all(
            "SELECT DISTINCT c.id, c.name FROM payments p "
            "JOIN students s ON s.id = p.student_id JOIN classes c ON c.id = s.class_id "
            "ORDER BY c.name COLLATE NOCASE")]
        return years, classes

    def history_page(self, search="", sort=None, desc=None, page=0, size=None,
                    school_year=None, class_id=None):
        self.ctx.session.require(self.read_perm)
        size = config.PAGE_SIZE if size is None else int(size)
        page = max(0, int(page))
        desc = self.default_desc if desc is None else desc
        rows = self.repo.page_filtered(
            search, sort, desc, size, page * size, school_year, class_id)
        total = self.repo.count_filtered(search, school_year, class_id)
        return Page(rows, total, page, size)

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

    def arrears_filter_options(self):
        self.ctx.session.require("payments.read")
        years = [r["school_year"] for r in self.db.all(
            "SELECT DISTINCT school_year FROM class_tuition_fees ORDER BY school_year DESC")]
        classes = [dict(r) for r in self.db.all(
            "SELECT c.id, c.name, c.school_year FROM classes c "
            "JOIN class_tuition_fees f ON f.class_id = c.id AND f.school_year = c.school_year "
            "ORDER BY c.name COLLATE NOCASE")]
        return years, classes

    # --- impayés détaillés ---
    def arrears(self, class_id=None, school_year=None, month=None, today=None):
        self.ctx.session.require("payments.read")
        today = today or date.today()
        if class_id is not None:
            class_id = V.integer({"class_id": class_id}, "class_id", "Classe", minimum=1)
            if self.db.one("SELECT id FROM classes WHERE id = ?", (class_id,)) is None:
                raise ValidationError("Classe inconnue.")
        if school_year is not None:
            school_year = V.school_year({"school_year": school_year}, "school_year")
        if month is not None:
            month = V.integer({"month": month}, "month", "Mois", minimum=1, maximum=12)
            if month not in school.SCHOOL_MONTHS:
                raise ValidationError("Mois hors année scolaire (septembre à juin).")

        where, params = [], []
        if class_id is not None:
            where.append("c.id = ?")
            params.append(class_id)
        if school_year is not None:
            where.append("c.school_year = ?")
            params.append(school_year)
        where.append("s.status = 'active'")
        where_sql = f" WHERE {' AND '.join(where)}"
        rows = self.db.all(
            "SELECT s.id, s.matricule, s.last_name, s.first_name, s.gender, s.tuition_discount, "
            "c.id AS class_id, c.name AS class_name, c.school_year, "
            "f.monthly_amount, f.droit_amount, f.photocopy_amount, f.uniform_amount, "
            "f.activity_1_amount, f.activity_2_amount, f.activity_3_amount, "
            "f.activity_4_amount, f.activity_5_amount "
            "FROM students s JOIN classes c ON c.id = s.class_id "
            "JOIN class_tuition_fees f ON f.class_id = c.id AND f.school_year = c.school_year"
            f"{where_sql} ORDER BY c.school_year DESC, c.name COLLATE NOCASE, s.last_name, s.first_name",
            params)
        payment_where, payment_params = [], []
        if class_id is not None:
            payment_where.append("s.class_id = ?")
            payment_params.append(class_id)
        if school_year is not None:
            payment_where.append("p.school_year = ?")
            payment_params.append(school_year)
        payment_filter = f" AND {' AND '.join(payment_where)}" if payment_where else ""
        paid_by_student = {}
        for payment in self.db.all(
            "SELECT p.student_id, p.school_year, p.fee_code, SUM(p.amount) AS paid "
            "FROM payments p JOIN students s ON s.id = p.student_id "
            "WHERE p.cancelled = 0" + payment_filter +
            " GROUP BY p.student_id, p.school_year, p.fee_code", payment_params):
            paid_by_student.setdefault((payment["student_id"], payment["school_year"]), {})[
                payment["fee_code"]] = payment["paid"]
        out = []
        for r in rows:
            payments = paid_by_student.get((r["id"], r["school_year"]), {})
            class_start = int(r["school_year"][:4])
            current_start = int(school.current_school_year(today)[:4])
            if class_start < current_start:
                months_due = len(school.SCHOOL_MONTHS)
            elif class_start > current_start:
                months_due = 0
            else:
                months_due = school.months_elapsed(today)
            if month is None and class_start <= current_start:
                for fee_code in (*school.CORE_FEE_CODES, *school.ACTIVITY_FEE_CODES):
                    due = r[school.FEE_AMOUNT_FIELDS[fee_code]]
                    self._append_arrear(out, r, fee_code, due, payments.get(fee_code, 0), None)
            if month is not None:
                candidate_months = (month,) if month in school.SCHOOL_MONTHS[:months_due] else ()
            else:
                candidate_months = school.SCHOOL_MONTHS[:months_due]
            for due_month in candidate_months:
                fee_code = school.MONTH_FEE_CODES[due_month]
                due = school.net_monthly(r["monthly_amount"], r["tuition_discount"])
                self._append_arrear(out, r, fee_code, due, payments.get(fee_code, 0), due_month)
        return sorted(out, key=lambda row: (-row["balance"], row["class_name"].casefold(),
                                            row["last_name"].casefold(), row["first_name"].casefold()))

    @staticmethod
    def _append_arrear(rows, student, fee_code, due, paid, month):
        balance = max(0, due - paid)
        if due > 0 and balance > 0:
            rows.append({
                "student_id": student["id"], "matricule": student["matricule"],
                "last_name": student["last_name"], "first_name": student["first_name"],
                "gender": student["gender"], "class_id": student["class_id"],
                "class_name": student["class_name"], "school_year": student["school_year"],
                "fee_code": fee_code,
                "fee_label": (f"Écolage — {school.MONTH_NAMES[month]}" if month
                              else school.FEE_ITEM_LABELS[fee_code]),
                "month": month, "due": due, "paid": paid, "balance": balance,
            })

    def export_arrears_csv(self, path, class_id=None, school_year=None, month=None, today=None):
        self.ctx.session.require("payments.export")
        rows = self.arrears(class_id, school_year, month, today)
        columns = (
            ("matricule", "Matricule"), ("last_name", "Nom"), ("first_name", "Prénom"),
            ("gender", "Sexe"), ("class_name", "Classe"), ("school_year", "Année scolaire"),
            ("fee_label", "Poste impayé"), ("month", "Mois"), ("due", "Dû (Ar)"),
            ("paid", "Payé (Ar)"), ("balance", "Reste à payer (Ar)"),
        )
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", newline="", encoding="utf-8-sig") as file:
            os.fchmod(file.fileno(), 0o600)
            writer = csv.writer(file)
            writer.writerow([label for _, label in columns])
            for row in rows:
                gender = {"M": "Masculin", "F": "Féminin"}.get(row["gender"], "")
                writer.writerow([
                    csv_safe(gender if key == "gender" else
                             school.MONTH_NAMES[row[key]] if key == "month" and row[key] else row[key])
                    for key, _ in columns
                ])
        self.log("export_arrears_csv", None, f"{len(rows)} lignes")
        return len(rows)
