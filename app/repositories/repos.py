from app.repositories.base import BaseRepository


class StudentRepository(BaseRepository):
    table = "students"
    columns = ("matricule", "first_name", "last_name", "birth_date", "gender", "tutor_name",
               "tutor_phone", "tutor_profession", "father_name", "father_phone", "father_profession",
               "mother_name", "mother_phone", "mother_profession",
               "tuition_discount", "address", "class_id", "status")
    extra_cols = ", c.name AS class_name, e.school_year AS school_year"
    joins = ("JOIN student_enrollments e ON e.student_id = t.id "
             "LEFT JOIN classes c ON c.id = e.class_id")
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
                "e.class_id, e.school_year, t.status, "
                "t.created_at, t.updated_at" + self.extra_cols +
                f" FROM {self.table} t {self.joins}")

    def page_for_year(self, school_year, search="", sort=None, desc=False, limit=100, offset=0):
        where, params = self._where(search)
        conditions = [where[7:]] if where else []
        conditions.append("e.school_year = ?")
        params.append(school_year)
        expr = self.sort_fields.get(sort, self.default_sort)
        direction = "DESC" if desc else "ASC"
        sql = (f"{self._select()} WHERE {' AND '.join(conditions)} "
               f"ORDER BY {expr} {direction}, t.id {direction} LIMIT ? OFFSET ?")
        return self.db.all(sql, [*params, int(limit), int(offset)])

    def count_for_year(self, school_year, search=""):
        where, params = self._where(search)
        conditions = [where[7:]] if where else []
        conditions.append("e.school_year = ?")
        params.append(school_year)
        return self.db.one(
            f"SELECT COUNT(*) AS n FROM students t {self.joins} "
            f"WHERE {' AND '.join(conditions)}", params)["n"]

    def get_for_year(self, id_, school_year):
        return self.db.one(
            f"{self._select()} WHERE t.id = ? AND e.school_year = ?", (id_, school_year))

    def count(self, search="") -> int:
        # student_enrollments est un join 1-N : on compte les élèves distincts.
        where, params = self._where(search)
        return self.db.one(
            f"SELECT COUNT(DISTINCT t.id) AS n FROM {self.table} t {self.joins}{where}",
            params)["n"]

    def get(self, id_):
        # Mêmes colonnes que _select (email/phone/guardian_name legacy exclus).
        return self.db.one(
            "SELECT t.id, t.matricule, t.first_name, t.last_name, t.birth_date, t.gender, "
            "t.tutor_name, t.father_name, t.mother_name, t.tuition_discount, t.address, "
            "t.tutor_phone, t.father_phone, t.mother_phone, "
            "t.tutor_profession, t.father_profession, t.mother_profession, "
            "t.status, t.created_at, t.updated_at, "
            "e.school_year, COALESCE(e.class_id, t.class_id) AS class_id, c.name AS class_name "
            "FROM students t "
            "LEFT JOIN student_enrollments e ON e.student_id=t.id "
            "LEFT JOIN classes c ON c.id=COALESCE(e.class_id,t.class_id) "
            "WHERE t.id=? ORDER BY e.school_year DESC LIMIT 1", (id_,))

    def years(self):
        return [r["school_year"] for r in self.db.all(
            "SELECT DISTINCT school_year FROM student_enrollments ORDER BY school_year DESC")]

    def enroll(self, student_id, class_id, school_year):
        self.db.execute(
            "INSERT INTO student_enrollments(student_id, school_year, class_id) VALUES(?,?,?)",
            (student_id, school_year, class_id))


class TeacherRepository(BaseRepository):
    table = "teachers"
    columns = ("employee_no", "first_name", "last_name", "gender", "birth_date", "birth_place",
               "phone", "address", "position", "hire_date")
    search_fields = ("t.last_name", "t.first_name", "t.employee_no")
    sort_fields = {"last_name": "t.last_name", "first_name": "t.first_name",
                   "employee_no": "t.employee_no", "position": "t.position",
                   "hire_date": "t.hire_date"}
    default_sort = "t.last_name"

    def page_for_year(self, school_year, search="", sort=None, desc=False, limit=100, offset=0):
        where, params = self._where(search)
        conditions = [where[7:]] if where else []
        conditions.append("y.school_year = ?")
        params.append(school_year)
        expr = self.sort_fields.get(sort, self.default_sort)
        direction = "DESC" if desc else "ASC"
        sql = (f"SELECT t.* FROM teachers t JOIN employee_school_years y "
               f"ON y.employee_id = t.id WHERE {' AND '.join(conditions)} "
               f"ORDER BY {expr} {direction}, t.id {direction} LIMIT ? OFFSET ?")
        return self.db.all(sql, [*params, int(limit), int(offset)])

    def count_for_year(self, school_year, search=""):
        where, params = self._where(search)
        conditions = [where[7:]] if where else []
        conditions.append("y.school_year = ?")
        params.append(school_year)
        return self.db.one(
            "SELECT COUNT(*) AS n FROM teachers t "
            "JOIN employee_school_years y ON y.employee_id = t.id "
            f"WHERE {' AND '.join(conditions)}", params)["n"]

    def get_for_year(self, id_, school_year):
        return self.db.one(
            "SELECT t.* FROM teachers t JOIN employee_school_years y ON y.employee_id=t.id "
            "WHERE t.id=? AND y.school_year=?", (id_, school_year))

    def years(self):
        return [r["school_year"] for r in self.db.all(
            "SELECT DISTINCT school_year FROM employee_school_years ORDER BY school_year DESC")]

    def assign_year(self, employee_id, school_year):
        self.db.execute(
            "INSERT OR IGNORE INTO employee_school_years(employee_id, school_year) VALUES(?,?)",
            (employee_id, school_year))

    def options_for_year(self, school_year):
        return [(r["label"], r["id"]) for r in self.db.all(
            "SELECT t.id, t.employee_no || ' - ' || t.last_name || ' ' || t.first_name AS label "
            "FROM teachers t JOIN employee_school_years y ON y.employee_id=t.id "
            "WHERE y.school_year=? ORDER BY t.last_name, t.first_name", (school_year,))]


class ClassRepository(BaseRepository):
    table = "classes"
    columns = ("name", "school_year", "capacity", "main_teacher_id")
    extra_cols = (", (SELECT COUNT(*) FROM student_enrollments e WHERE e.class_id = t.id) AS student_count,"
                  " (m.employee_no || ' - ' || m.last_name || ' ' || m.first_name) AS employee")
    joins = "LEFT JOIN teachers m ON m.id = t.main_teacher_id"
    search_fields = ("t.name",)
    sort_fields = {"name": "t.name", "school_year": "t.school_year",
                   "student_count": "student_count", "capacity": "t.capacity",
                   "employee": "employee"}
    default_sort = "t.name"

    def page_for_year(self, school_year, search="", sort=None, desc=False, limit=100, offset=0):
        where, params = self._where(search)
        conditions = [where[7:]] if where else []
        conditions.append("t.school_year = ?")
        params.append(school_year)
        expr = self.sort_fields.get(sort, self.default_sort)
        direction = "DESC" if desc else "ASC"
        sql = (f"{self._select()} WHERE {' AND '.join(conditions)} "
               f"ORDER BY {expr} {direction}, t.id {direction} LIMIT ? OFFSET ?")
        return self.db.all(sql, [*params, int(limit), int(offset)])

    def count_for_year(self, school_year, search=""):
        where, params = self._where(search)
        conditions = [where[7:]] if where else []
        conditions.append("t.school_year = ?")
        params.append(school_year)
        return self.db.one(
            f"SELECT COUNT(*) AS n FROM classes t WHERE {' AND '.join(conditions)}", params)["n"]

    def years(self):
        return [r["school_year"] for r in self.db.all(
            "SELECT DISTINCT school_year FROM classes ORDER BY school_year DESC")]

    def options_for_year(self, school_year):
        return [(r["label"], r["id"]) for r in self.db.all(
            "SELECT id, name AS label FROM classes WHERE school_year=? ORDER BY name",
            (school_year,))]

    def class_year(self, class_id):
        row = self.db.one("SELECT school_year FROM classes WHERE id=?", (class_id,))
        return row["school_year"] if row else None

    def class_year_options(self):
        return [dict(row) for row in self.db.all(
            "SELECT id, name, school_year FROM classes "
            "ORDER BY school_year DESC, name COLLATE NOCASE")]



class AttendanceRepository(BaseRepository):
    table = "employee_attendance"
    columns = ("employee_id", "attendance_date", "status", "arrival_time", "departure_time", "comment")
    extra_cols = (", (e.employee_no || ' - ' || e.last_name || ' ' || e.first_name) AS employee_label,"
                  " e.employee_no, e.last_name, e.first_name")
    joins = "LEFT JOIN teachers e ON e.id = t.employee_id"
    search_fields = ("e.last_name", "e.first_name", "e.employee_no", "t.attendance_date")
    sort_fields = {"attendance_date": "t.attendance_date", "employee_label": "e.last_name",
                   "status": "t.status", "arrival_time": "t.arrival_time"}
    default_sort = "t.attendance_date"


class SalaryRepository(BaseRepository):
    table = "employee_salaries"
    columns = ("employee_id", "pay_type", "monthly_amount", "hourly_rate")
    extra_cols = (", (e.employee_no || ' - ' || e.last_name || ' ' || e.first_name) AS employee_label,"
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
            "UPDATE users SET "
            "locked_until = CASE WHEN failed_attempts + 1 >= ? THEN ? ELSE locked_until END, "
            "failed_attempts = CASE WHEN failed_attempts + 1 >= ? THEN 0 ELSE failed_attempts + 1 END "
            "WHERE id = ?", (max_attempts, locked_until, max_attempts, id_))

    def reset_failures(self, id_):
        self.db.execute("UPDATE users SET failed_attempts=0, locked_until=NULL WHERE id=?", (id_,))

    def set_password(self, id_, password_hash, must_change=False):
        self.db.execute("UPDATE users SET password_hash=?, must_change_password=? WHERE id=?",
                        (password_hash, int(must_change), id_))
