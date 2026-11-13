from app.repositories.base import BaseRepository


class TuitionFeeRepository(BaseRepository):
    table = "tuition_fees"
    columns = ("level", "school_year", "monthly_amount", "registration_fee")
    search_fields = ("t.level", "t.school_year")
    sort_fields = {"level": "t.level", "school_year": "t.school_year", "monthly_amount": "t.monthly_amount"}
    default_sort = "t.school_year"


class PaymentRepository(BaseRepository):
    table = "payments"
    columns = ("receipt_no", "student_id", "school_year", "kind", "month", "amount", "method",
               "reference", "received_by")
    extra_cols = ", (s.last_name || ' ' || s.first_name) AS student_name, s.matricule AS matricule"
    joins = "JOIN students s ON s.id = t.student_id"
    search_fields = ("t.receipt_no",)
    sort_fields = {"receipt_no": "t.receipt_no", "paid_at": "t.paid_at", "amount": "t.amount"}
    default_sort = "t.id"
