"""Écolages : tarifs par niveau, encaissements, reçus, annulations, impayés, charges."""
import csv
import heapq
import os
from datetime import date

from app import config
from app.core import school
from app.core import validators as V
from app.core.exceptions import NotFoundError, ValidationError
from app.repositories.finance_repos import (ExpenseRepository, PaymentRepository,
                                            TuitionFeeRepository)
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
            "SELECT id, name || ' - ' || school_year AS label FROM classes ORDER BY name")]


class PaymentService(CrudService):
    """Lecture/liste via CrudService ; l'écriture passe uniquement par record() et cancel()."""
    entity = "payments"
    repo_cls = PaymentRepository
    read_perm = "payments.read"
    default_desc = True

    def history_filter_options(self, school_year=None):
        self.ctx.session.require(self.read_perm)
        if school_year is not None:
            school_year = V.school_year({"school_year": school_year}, "school_year")
        years = [r["school_year"] for r in self.db.all(
            "SELECT DISTINCT school_year FROM payments ORDER BY school_year DESC")]
        params = ()
        year_filter = ""
        if school_year is not None:
            year_filter = "AND p.school_year = ? "
            params = (school_year,)
        classes = [dict(r) for r in self.db.all(
            "SELECT DISTINCT c.id, c.name, c.school_year FROM payments p "
            "JOIN students s ON s.id = p.student_id "
            "LEFT JOIN student_enrollments e ON e.student_id=s.id AND e.school_year=p.school_year "
            "JOIN classes c ON c.id = COALESCE(e.class_id,s.class_id) "
            f"{year_filter}ORDER BY c.name COLLATE NOCASE, c.school_year DESC", params)]
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
    def statement(self, student_id, school_year=None):
        self.ctx.session.require("payments.read")
        if school_year is not None:
            school_year = V.school_year({"school_year": school_year}, "school_year")
        year_filter = ""
        params = [int(student_id)]
        if school_year is not None:
            year_filter = "AND e.school_year = ? "
            params.append(school_year)
        st = self.db.one(
            "SELECT s.id, s.matricule, s.last_name, s.first_name, s.tuition_discount, "
            "e.class_id, c.name AS class_name, e.school_year FROM students s "
            "JOIN student_enrollments e ON e.student_id=s.id "
            "LEFT JOIN classes c ON c.id=e.class_id WHERE s.id=? "
            f"{year_filter}ORDER BY e.school_year DESC LIMIT 1", params)
        if st is None:
            if school_year is not None:
                raise NotFoundError("Élève non inscrit pour cette année scolaire.")
            raise NotFoundError("Élève introuvable.")
        if st["class_id"] is None:
            raise ValidationError("Cet élève n'a pas de classe : impossible de calculer l'écolage.")
        fee = self.db.one("SELECT * FROM class_tuition_fees WHERE class_id = ? AND school_year = ?",
                          (st["class_id"], st["school_year"]))
        if fee is None:
            raise ValidationError(f"Aucun tarif défini pour la classe {st['class_name']} "
                                  f"{st['school_year']} (onglet Tarifs).")
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
    def record(self, student_id, data, school_year=None):
        user = self.ctx.session.require("payments.write")
        if school_year is not None:
            school_year = V.school_year({"school_year": school_year}, "school_year")
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
            st = self.statement(student_id, school_year)
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

    def receipt_data(self, payment_id):
        self.ctx.session.require("payments.read")
        r = self.db.one(
            "SELECT p.*, s.matricule, s.last_name, s.first_name, c.name AS class_name, "
            "u.full_name AS cashier FROM payments p JOIN students s ON s.id = p.student_id "
            "LEFT JOIN student_enrollments e ON e.student_id=s.id AND e.school_year=p.school_year "
            "LEFT JOIN classes c ON c.id=COALESCE(e.class_id,s.class_id) "
            "LEFT JOIN users u ON u.id = p.received_by "
            "WHERE p.id = ?", (int(payment_id),))
        if r is None:
            raise NotFoundError("Paiement introuvable.")
        return dict(r)

    def arrears_filter_options(self, school_year=None):
        self.ctx.session.require("payments.read")
        if school_year is not None:
            school_year = V.school_year({"school_year": school_year}, "school_year")
        years = [r["school_year"] for r in self.db.all(
            "SELECT DISTINCT school_year FROM class_tuition_fees ORDER BY school_year DESC")]
        params = ()
        year_filter = ""
        if school_year is not None:
            year_filter = "WHERE c.school_year = ? "
            params = (school_year,)
        classes = [dict(r) for r in self.db.all(
            "SELECT c.id, c.name, c.school_year FROM classes c "
            "JOIN class_tuition_fees f ON f.class_id = c.id AND f.school_year = c.school_year "
            f"{year_filter}ORDER BY c.name COLLATE NOCASE", params)]
        return years, classes

    def _iter_arrears(self, class_id=None, school_year=None, month=None, today=None):
        """Génère les impayés ligne à ligne : une école entière reste en mémoire
        bornée (seule la page demandée est conservée), sans tout matérialiser."""
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

        # La classe/année d'un élève se lit dans ses inscriptions (une par année),
        # pas dans students.class_id qui ne reflète que l'année courante.
        where, params = [], []
        if class_id is not None:
            where.append("c.id = ?")
            params.append(class_id)
        if school_year is not None:
            where.append("c.school_year = ?")
            params.append(school_year)
        where.append("s.status = 'active'")
        students_sql = (
            "SELECT s.id AS student_id, s.matricule, s.last_name, s.first_name, s.gender, "
            "s.tuition_discount, c.id AS class_id, c.name AS class_name, c.school_year, "
            "f.monthly_amount, f.droit_amount, f.photocopy_amount, f.uniform_amount, "
            "f.activity_1_amount, f.activity_2_amount, f.activity_3_amount, "
            "f.activity_4_amount, f.activity_5_amount "
            "FROM students s JOIN student_enrollments e ON e.student_id = s.id "
            "JOIN classes c ON c.id = e.class_id "
            "JOIN class_tuition_fees f ON f.class_id = c.id AND f.school_year = c.school_year "
            f"WHERE {' AND '.join(where)} "
            "ORDER BY c.school_year DESC, c.name COLLATE NOCASE, s.last_name COLLATE NOCASE, "
            "s.first_name COLLATE NOCASE, s.id")
        payments_where = ["p.cancelled = 0", "s.status = 'active'"]
        payment_params = []
        enrollment_join = ""
        if class_id is not None:
            enrollment_join = ("LEFT JOIN student_enrollments e "
                               "ON e.student_id = s.id AND e.school_year = p.school_year ")
            payments_where.append("COALESCE(e.class_id, s.class_id) = ?")
            payment_params.append(class_id)
        if school_year is not None:
            payments_where.append("p.school_year = ?")
            payment_params.append(school_year)
        payments_sql = (
            "SELECT p.student_id, p.school_year, p.fee_code, SUM(p.amount) AS paid "
            "FROM payments p JOIN students s ON s.id = p.student_id "
            f"{enrollment_join}"
            f"WHERE {' AND '.join(payments_where)} "
            "GROUP BY p.student_id, p.school_year, p.fee_code")
        paid_by_student = {
            (payment["student_id"], payment["school_year"], payment["fee_code"]): payment["paid"]
            for payment in self.db.all(payments_sql, payment_params)}

        current_start = int(school.current_school_year(today)[:4])
        elapsed = school.months_elapsed(today)
        school_month_index = {
            school_month: index for index, school_month in enumerate(school.SCHOOL_MONTHS, start=1)}
        fixed_fee_codes = (*school.CORE_FEE_CODES, *school.ACTIVITY_FEE_CODES)

        def append_arrear(student, fee_code, due, due_month):
            paid = paid_by_student.get(
                (student["student_id"], student["school_year"], fee_code), 0)
            balance = max(0, due - paid)
            if due <= 0 or balance <= 0:
                return None
            return {
                "student_id": student["student_id"],
                "matricule": student["matricule"],
                "last_name": student["last_name"],
                "first_name": student["first_name"],
                "gender": student["gender"],
                "class_id": student["class_id"],
                "class_name": student["class_name"],
                "school_year": student["school_year"],
                "fee_code": fee_code,
                "fee_label": (f"Écolage - {school.MONTH_NAMES[due_month]}" if due_month
                              else school.FEE_ITEM_LABELS[fee_code]),
                "month": due_month,
                "due": due,
                "paid": paid,
                "balance": balance,
            }

        def generate():
            cursor = self.db.conn.execute(students_sql, params)
            try:
                while batch := cursor.fetchmany(1000):
                    for student in batch:
                        class_start = int(student["school_year"][:4])
                        if class_start < current_start:
                            months_due = len(school.SCHOOL_MONTHS)
                        elif class_start == current_start:
                            months_due = elapsed
                        else:
                            months_due = 0
                        if month is None and class_start <= current_start:
                            for fee_code in fixed_fee_codes:
                                row = append_arrear(
                                    student, fee_code, student[school.FEE_AMOUNT_FIELDS[fee_code]],
                                    None)
                                if row is not None:
                                    yield row
                        if month is None:
                            candidate_months = school.SCHOOL_MONTHS[:months_due]
                        elif school_month_index[month] <= months_due:
                            candidate_months = (month,)
                        else:
                            candidate_months = ()
                        for due_month in candidate_months:
                            fee_code = school.MONTH_FEE_CODES[due_month]
                            due = school.net_monthly(
                                student["monthly_amount"], student["tuition_discount"])
                            row = append_arrear(student, fee_code, due, due_month)
                            if row is not None:
                                yield row
            finally:
                cursor.close()

        return generate()

    @staticmethod
    def _arrears_sort_key(row):
        return (-row["balance"], row["class_name"].casefold(), row["last_name"].casefold(),
                row["first_name"].casefold(), row["student_id"], row["fee_code"])

    def arrears(self, class_id=None, school_year=None, month=None, today=None):
        return sorted(self._iter_arrears(class_id, school_year, month, today),
                      key=self._arrears_sort_key)

    def arrears_page(self, class_id=None, school_year=None, month=None, today=None,
                     page=0, size=config.PAGE_SIZE):
        page = max(0, int(page))
        size = max(1, int(size))
        unique_students = set()
        total_balance = 0
        total = 0

        def count_rows():
            nonlocal total, total_balance
            for row in self._iter_arrears(class_id, school_year, month, today):
                total += 1
                total_balance += row["balance"]
                unique_students.add(row["student_id"])
                yield row

        # On ne trie que le strict nécessaire (page courante incluse) plutôt que
        # l'intégralité du rapport : reste dans l'ordre exact de arrears().
        limit = (page + 1) * size
        page_rows = heapq.nsmallest(limit, count_rows(), key=self._arrears_sort_key)
        pages = max(1, (total + size - 1) // size)
        return {
            "rows": page_rows[page * size:(page + 1) * size],
            "total": total,
            "students": len(unique_students),
            "balance": total_balance,
            "page": page,
            "pages": pages,
        }

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
                             school.MONTH_NAMES[row[key]] if key == "month" and row[key]
                             else row[key])
                    for key, _ in columns
                ])
        return len(rows)


class ExpenseService(CrudService):
    """Charges d'exploitation saisies (loyer, électricité, eau, autres)."""
    entity = "expenses"
    repo_cls = ExpenseRepository
    read_perm, write_perm, delete_perm = "expenses.read", "expenses.write", "expenses.delete"
    default_desc = True

    def validate(self, data):
        return {
            "category": V.choice(data, "category", "Catégorie", tuple(school.EXPENSE_CATEGORIES)),
            "label": V.text(data, "label", "Libellé", required=False, max_len=120) or "",
            "amount": V.integer(data, "amount", "Montant", required=True, minimum=1,
                                maximum=school.MAX_AMOUNT),
            "expense_date": V.date_iso(data, "expense_date", "Date"),
        }

    def prepare(self, clean):
        clean["created_by"] = self.user.id
        return clean
