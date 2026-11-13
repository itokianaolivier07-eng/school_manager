"""Enseignants, classes et matières."""
from app.core import validators as V
from app.repositories.repos import ClassRepository, SubjectRepository, TeacherRepository
from app.services.base import CrudService


class _OptionsMixin:
    option_sql = ""

    def options(self):
        self.ctx.session.require(self.read_perm)
        return [(r["label"], r["id"]) for r in self.db.all(self.option_sql)]


class TeacherService(_OptionsMixin, CrudService):
    entity = "teachers"
    repo_cls = TeacherRepository
    read_perm, write_perm, delete_perm = "teachers.read", "teachers.write", "teachers.delete"
    option_sql = "SELECT id, last_name || ' ' || first_name AS label FROM teachers ORDER BY last_name"

    def validate(self, data):
        return {
            "employee_no": V.text(data, "employee_no", "N° employé", max_len=20, upper=True,
                                  pattern=V.CODE_RE),
            "first_name": V.text(data, "first_name", "Prénom", max_len=60, pattern=V.NAME_RE),
            "last_name": V.text(data, "last_name", "Nom", max_len=60, pattern=V.NAME_RE),
            "email": V.text(data, "email", "E-mail", required=False, max_len=120, pattern=V.EMAIL_RE),
            "phone": V.text(data, "phone", "Téléphone", required=False, max_len=20, pattern=V.PHONE_RE),
            "speciality": V.text(data, "speciality", "Spécialité", required=False, max_len=80),
            "hire_date": V.date_iso(data, "hire_date", "Date d'embauche", required=False),
        }


class ClassService(_OptionsMixin, CrudService):
    entity = "classes"
    repo_cls = ClassRepository
    read_perm, write_perm, delete_perm = "classes.read", "classes.write", "classes.delete"
    option_sql = "SELECT id, name AS label FROM classes ORDER BY name"

    def validate(self, data):
        return {
            "name": V.text(data, "name", "Nom de la classe", max_len=40),
            "level": V.text(data, "level", "Niveau", required=False, max_len=40),
            "school_year": V.text(data, "school_year", "Année scolaire", max_len=9,
                                  pattern=V.YEAR_RE, error="Année scolaire : format AAAA-AAAA."),
            "main_teacher_id": V.integer(data, "main_teacher_id", "Titulaire", minimum=1),
        }


class SubjectService(_OptionsMixin, CrudService):
    entity = "subjects"
    repo_cls = SubjectRepository
    read_perm, write_perm, delete_perm = "subjects.read", "subjects.write", "subjects.delete"
    option_sql = "SELECT id, name AS label FROM subjects ORDER BY name"

    def validate(self, data):
        return {
            "code": V.text(data, "code", "Code", max_len=20, upper=True, pattern=V.CODE_RE),
            "name": V.text(data, "name", "Nom de la matière", max_len=80),
            "coefficient": V.number(data, "coefficient", "Coefficient", minimum=0.5, maximum=20),
            "teacher_id": V.integer(data, "teacher_id", "Enseignant", minimum=1),
        }
