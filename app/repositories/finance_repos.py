from app.repositories.base import BaseRepository


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
    extra_cols = ", (s.last_name || ' ' || s.first_name) AS student_name, s.matricule AS matricule"
    joins = "JOIN students s ON s.id = t.student_id"
    search_fields = ("t.receipt_no",)
    sort_fields = {"receipt_no": "t.receipt_no", "paid_at": "t.paid_at", "amount": "t.amount"}
    default_sort = "t.id"
