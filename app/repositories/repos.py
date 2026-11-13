from app.repositories.base import BaseRepository


class StudentRepository(BaseRepository):
    table = "students"
    columns = ("matricule", "first_name", "last_name", "birth_date", "gender", "tutor_name",
               "father_name", "mother_name",
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
                "t.class_id, t.status, "
                "t.created_at, t.updated_at" + self.extra_cols +
                f" FROM {self.table} t {self.joins}")


class TeacherRepository(BaseRepository):
    table = "teachers"
    columns = ("employee_no", "first_name", "last_name", "gender", "birth_date", "birth_place",
               "phone", "address", "position", "hire_date")
    search_fields = ("t.last_name", "t.first_name", "t.employee_no")
    sort_fields = {"last_name": "t.last_name", "first_name": "t.first_name",
                   "employee_no": "t.employee_no", "position": "t.position"}
    default_sort = "t.last_name"


class ClassRepository(BaseRepository):
    table = "classes"
    columns = ("name", "school_year", "capacity", "main_teacher_id")
    extra_cols = (", (SELECT COUNT(*) FROM students s WHERE s.class_id = t.id) AS student_count,"
                  " (m.employee_no || ' — ' || m.last_name || ' ' || m.first_name) AS employee")
    joins = "LEFT JOIN teachers m ON m.id = t.main_teacher_id"
    search_fields = ("t.name",)
    sort_fields = {"name": "t.name", "school_year": "t.school_year",
                   "student_count": "student_count", "capacity": "t.capacity"}
    default_sort = "t.name"


class SubjectRepository(BaseRepository):
    table = "subjects"
    columns = ("code", "name", "coefficient", "teacher_id")
    extra_cols = ", (m.last_name || ' ' || m.first_name) AS teacher_name"
    joins = "LEFT JOIN teachers m ON m.id = t.teacher_id"
    search_fields = ("t.code", "t.name")
    sort_fields = {"code": "t.code", "name": "t.name", "coefficient": "t.coefficient"}
    default_sort = "t.name"


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
        self.db.execute(
            "INSERT INTO audit_log(user_id, username, action, entity, entity_id, details) "
            "VALUES (?,?,?,?,?,?)",
            (user.id if user else None, user.username if user else username,
             action, entity, entity_id, details))
