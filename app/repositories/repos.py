from app.repositories.base import BaseRepository


class StudentRepository(BaseRepository):
    table = "students"
    columns = ("matricule", "first_name", "last_name", "birth_date", "gender", "tutor_name",
               "tutor_phone", "tutor_profession", "father_name", "father_phone", "father_profession",
               "mother_name", "mother_phone", "mother_profession",
               "tuition_discount", "address", "class_id", "status")
    extra_cols = ", c.name AS class_name"
    joins = "LEFT JOIN classes c ON c.id = t.class_id"
    search_fields = ("t.last_name", "t.first_name", "t.matricule")
    sort_fields = {"last_name": "t.last_name", "first_name": "t.first_name",
                   "matricule": "t.matricule", "birth_date": "t.birth_date",
                   "class_name": "c.name", "status": "t.status"}
    default_sort = "t.last_name"

    def _select(self):
        return ("SELECT t.id, t.matricule, t.first_name, t.last_name, t.birth_date, t.gender, "
                "t.tutor_name, t.father_name, t.mother_name, t.tuition_discount, t.address, "
                "t.tutor_phone, t.father_phone, t.mother_phone, "
                "t.tutor_profession, t.father_profession, t.mother_profession, "
                "t.class_id, t.status, "
                "t.created_at, t.updated_at" + self.extra_cols +
                f" FROM {self.table} t {self.joins}")


class TeacherRepository(BaseRepository):
    table = "teachers"
    columns = ("employee_no", "first_name", "last_name", "gender", "birth_date", "birth_place",
               "phone", "address", "position", "hire_date")
    search_fields = ("t.last_name", "t.first_name", "t.employee_no")
    sort_fields = {"last_name": "t.last_name", "first_name": "t.first_name",
                   "employee_no": "t.employee_no", "position": "t.position",
                   "hire_date": "t.hire_date"}
    default_sort = "t.last_name"


class ClassRepository(BaseRepository):
    table = "classes"
    columns = ("name", "school_year", "capacity", "main_teacher_id")
    extra_cols = (", (SELECT COUNT(*) FROM students s WHERE s.class_id = t.id) AS student_count,"
                  " (m.employee_no || ' — ' || m.last_name || ' ' || m.first_name) AS employee")
    joins = "LEFT JOIN teachers m ON m.id = t.main_teacher_id"
    search_fields = ("t.name",)
    sort_fields = {"name": "t.name", "school_year": "t.school_year",
                   "student_count": "student_count", "capacity": "t.capacity",
                   "employee": "employee"}
    default_sort = "t.name"


class AttendanceRepository(BaseRepository):
    table = "employee_attendance"
    columns = ("employee_id", "attendance_date", "status", "arrival_time", "departure_time", "comment")
    extra_cols = (", (e.employee_no || ' — ' || e.last_name || ' ' || e.first_name) AS employee_label,"
                  " e.employee_no, e.last_name, e.first_name")
    joins = "LEFT JOIN teachers e ON e.id = t.employee_id"
    search_fields = ("e.last_name", "e.first_name", "e.employee_no", "t.attendance_date")
    sort_fields = {"attendance_date": "t.attendance_date", "employee_label": "e.last_name",
                   "status": "t.status", "arrival_time": "t.arrival_time"}
    default_sort = "t.attendance_date"


class SalaryRepository(BaseRepository):
    table = "employee_salaries"
    columns = ("employee_id", "pay_type", "monthly_amount", "hourly_rate")
    extra_cols = (", (e.employee_no || ' — ' || e.last_name || ' ' || e.first_name) AS employee_label,"
                  " e.employee_no, e.last_name, e.first_name, e.position,"
                  " CASE WHEN lower(COALESCE(e.position, '')) LIKE '%prof%' THEN 'hourly' "
                  "ELSE 'monthly' END AS pay_type,"
                  " CASE WHEN lower(COALESCE(e.position, '')) LIKE '%prof%' "
                  "THEN t.hourly_rate ELSE t.monthly_amount END AS base_amount")
    joins = "LEFT JOIN teachers e ON e.id = t.employee_id"
    search_fields = ("e.last_name", "e.first_name", "e.employee_no")
    sort_fields = {"employee_label": "e.last_name", "base_amount": "base_amount",
                   "updated_at": "t.updated_at"}
    default_sort = "e.last_name"

    def _select(self):
        return (f"SELECT t.id, t.employee_id, t.monthly_amount, t.hourly_rate, t.updated_at"
                f"{self.extra_cols} FROM {self.table} t {self.joins}")


class SalaryDisbursementRepository(BaseRepository):
    table = "salary_disbursements"
    columns = ("employee_id", "title", "payout_date", "school_year", "hours",
               "hourly_rate", "amount", "created_by")
    extra_cols = (", e.employee_no, (e.last_name || ' ' || e.first_name) AS employee_name, "
                  "e.position")
    joins = "JOIN teachers e ON e.id = t.employee_id"
    search_fields = ("e.employee_no", "e.last_name", "e.first_name", "t.title")
    sort_fields = {"employee_no": "e.employee_no", "employee_name": "e.last_name",
                   "title": "t.title", "payout_date": "t.payout_date",
                   "school_year": "t.school_year", "amount": "t.amount"}
    default_sort = "t.payout_date"
    default_desc = True


class UserRepository(BaseRepository):
    table = "users"
    columns = ("username", "password_hash", "full_name", "role", "is_active", "must_change_password")
    search_fields = ("t.username", "t.full_name")
    sort_fields = {"username": "t.username", "full_name": "t.full_name", "role": "t.role"}
    default_sort = "t.username"

    def _select(self):
        return ("SELECT t.id, t.username, t.full_name, t.role, t.is_active, "
                "t.must_change_password, t.created_at FROM users t")

    def get_by_username(self, username):
        return self.db.one("SELECT * FROM users WHERE username = ?", (username,))

    def count_all(self) -> int:
        return self.db.one("SELECT COUNT(*) AS n FROM users")["n"]

    def count_active_admins(self, excluding_id=None) -> int:
        return self.db.one("SELECT COUNT(*) AS n FROM users WHERE role='admin' AND is_active=1 "
                           "AND id != ?", (excluding_id or -1,))["n"]

    def register_failure(self, id_, max_attempts, locked_until):
        self.db.execute(
            "UPDATE users SET failed_attempts = failed_attempts + 1, "
            "locked_until = CASE WHEN failed_attempts + 1 >= ? THEN ? ELSE locked_until END "
            "WHERE id = ?", (max_attempts, locked_until, id_))

    def reset_failures(self, id_):
        self.db.execute("UPDATE users SET failed_attempts=0, locked_until=NULL WHERE id=?", (id_,))

    def set_password(self, id_, password_hash, must_change=False):
        self.db.execute("UPDATE users SET password_hash=?, must_change_password=? WHERE id=?",
                        (password_hash, int(must_change), id_))


class AuditRepository(BaseRepository):
    table = "audit_log"
    columns = ()
    search_fields = ("t.username", "t.action", "t.entity")
    sort_fields = {"ts": "t.id", "username": "t.username", "action": "t.action",
                   "entity": "t.entity"}
    default_sort = "t.id"

    def log(self, user, action, entity=None, entity_id=None, details=None, username=None):
        uname = username or (user.username if user else None)
        uid = user.id if user else None
        self.db.execute(
            "INSERT INTO audit_log(user_id, username, action, entity, entity_id, details) "
            "VALUES (?,?,?,?,?,?)",
            (uid, uname, action, entity, entity_id, details))
