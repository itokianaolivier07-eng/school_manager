from app.core import school
from app.repositories.base import BaseRepository


def _fee_due_cases():
    cases = []
    for fee_code in school.FEE_ITEM_CODES:
        month = school.MONTHS_BY_FEE_CODE.get(fee_code)
        if month is not None:
            amount = "CAST(f.monthly_amount * (100 - s.tuition_discount) / 100 AS INTEGER)"
        else:
            amount = f"f.{school.FEE_AMOUNT_FIELDS[fee_code]}"
        cases.append(f"WHEN '{fee_code}' THEN {amount}")
    return cases


class TuitionFeeRepository(BaseRepository):
    table = "class_tuition_fees"
    columns = ("class_id", "school_year", "monthly_amount", "droit_amount", "photocopy_amount",
               "uniform_amount", "activity_1_amount", "activity_2_amount", "activity_3_amount",
               "activity_4_amount", "activity_5_amount")
    extra_cols = ", c.name AS class_name"
    joins = "JOIN classes c ON c.id = t.class_id"
    search_fields = ("c.name", "t.school_year")
    sort_fields = {"class_name": "c.name", "school_year": "t.school_year",
                   "monthly_amount": "t.monthly_amount"}
    default_sort = "c.name"


class PaymentRepository(BaseRepository):
    table = "payments"
    columns = ("receipt_no", "student_id", "school_year", "kind", "month", "fee_code", "amount", "method",
               "reference", "received_by")
    extra_cols = (", c.name AS class_name, (s.last_name || ' ' || s.first_name) AS student_name, "
                  "s.matricule AS matricule, "
                  "s.gender AS gender, "
                  "CASE WHEN t.cancelled = 1 THEN 'Annulé' "
                  "WHEN COALESCE((SELECT SUM(p.amount) FROM payments p "
                  "WHERE p.student_id = t.student_id AND p.school_year = t.school_year "
                  "AND p.fee_code = t.fee_code AND p.cancelled = 0), 0) >= "
                  f"(CASE t.fee_code {' '.join(_fee_due_cases())} END) "
                  "THEN 'Payé totalement' ELSE 'Partiel' END AS payment_status")
    joins = ("JOIN students s ON s.id = t.student_id "
             "LEFT JOIN classes c ON c.id = s.class_id "
             "LEFT JOIN class_tuition_fees f ON f.class_id = s.class_id AND f.school_year = t.school_year")
    search_fields = ("t.receipt_no",)
    sort_fields = {"class_name": "c.name", "school_year": "t.school_year",
                   "receipt_no": "t.receipt_no", "paid_at": "t.paid_at", "amount": "t.amount"}
    default_sort = "t.id"

    def page(self, search="", sort=None, desc=False, limit=100, offset=0):
        return self.page_filtered(search, sort, desc, limit, offset)

    def page_filtered(self, search="", sort=None, desc=False, limit=100, offset=0,
                      school_year=None, class_id=None):
        where, params = self._filter_where(search, school_year, class_id)
        if sort is None:
            order = "c.name COLLATE NOCASE ASC, t.school_year DESC, t.paid_at DESC, t.id DESC"
        else:
            expr = self.sort_fields.get(sort, self.default_sort)
            direction = "DESC" if desc else "ASC"
            order = (f"{expr} {direction}, c.name COLLATE NOCASE ASC, "
                     f"t.school_year DESC, t.id DESC")
        sql = f"{self._select()}{where} ORDER BY {order} LIMIT ? OFFSET ?"
        return self.db.all(sql, [*params, int(limit), int(offset)])

    def count_filtered(self, search="", school_year=None, class_id=None):
        where, params = self._filter_where(search, school_year, class_id)
        return self.db.one(
            f"SELECT COUNT(*) AS n FROM {self.table} t {self.joins}{where}", params)["n"]

    def _filter_where(self, search, school_year, class_id):
        where, params = self._where(search)
        conditions = [where[7:]] if where else []
        if school_year is not None:
            conditions.append("t.school_year = ?")
            params.append(school_year)
        if class_id is not None:
            conditions.append("s.class_id = ?")
            params.append(int(class_id))
        return (f" WHERE {' AND '.join(conditions)}" if conditions else ""), params
