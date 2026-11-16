"""Employés et classes."""
import sqlite3

from app.core import validators as V
from app.core import school
from app.core.exceptions import NotFoundError, ValidationError
from app.repositories.base import used_school_years
from app.repositories.repos import ClassRepository, TeacherRepository
from app.services.audit import clean_detail, log_event
from app.services.base import CrudService, Page, translate_integrity


class _OptionsMixin:
    option_sql = ""

    def options(self):
        self.ctx.session.require(self.read_perm)
        return [(r["label"], r["id"]) for r in self.db.all(self.option_sql)]


class TeacherService(_OptionsMixin, CrudService):
    entity = "teachers"
    repo_cls = TeacherRepository
    read_perm, write_perm, delete_perm = "teachers.read", "teachers.write", "teachers.delete"
    option_sql = ("SELECT id, employee_no || ' - ' || last_name || ' ' || first_name AS label "
                  "FROM teachers ORDER BY last_name, first_name")

    def __init__(self, ctx):
        super().__init__(ctx)
        self.school_year = school.current_school_year()

    def school_year_options(self):
        return used_school_years(self.db)

    def select_school_year(self, school_year):
        self.school_year = school_year or school.current_school_year()

    def page(self, search="", sort=None, desc=None, page=0, size=100):
        self.ctx.session.require(self.read_perm)
        page = max(0, int(page))
        desc = self.default_desc if desc is None else desc
        rows = self.repo.page_for_year(
            self.school_year, search, sort, desc, size, page * size)
        total = self.repo.count_for_year(self.school_year, search)
        return Page(rows, total, page, size)

    def get(self, id_):
        self.ctx.session.require(self.read_perm)
        row = self.repo.get_for_year(id_, self.school_year)
        if row is None:
            raise NotFoundError("Employé introuvable pour cette année scolaire.")
        return dict(row)

    def create(self, data):
        self.ctx.session.require(self.write_perm)
        clean = self.validate(data)
        with self.db.transaction():
            try:
                employee_id = self.repo.insert(clean)
                self.repo.assign_year(employee_id, self.school_year)
            except sqlite3.IntegrityError as e:
                raise translate_integrity(e) from e
            log_event(self.ctx, "create", self.entity, employee_id, clean_detail(clean))
        return employee_id

    def assign_year(self, employee_id, school_year):
        self.ctx.session.require(self.write_perm)
        school_year = V.school_year({"school_year": school_year}, "school_year")
        with self.db.transaction():
            if self.db.one("SELECT id FROM teachers WHERE id=?", (employee_id,)) is None:
                raise NotFoundError("Employé introuvable.")
            self.repo.assign_year(employee_id, school_year)

    def remove_year(self, employee_id, school_year):
        self.ctx.session.require(self.write_perm)
        school_year = V.school_year({"school_year": school_year}, "school_year")
        with self.db.transaction():
            if self.db.one(
                    "SELECT id FROM classes WHERE school_year=? AND main_teacher_id=?",
                    (school_year, employee_id)):
                raise ValidationError("Retirez d'abord l'employé des classes de cette année.")
            changed = self.db.execute(
                "DELETE FROM employee_school_years WHERE employee_id=? AND school_year=?",
                (employee_id, school_year)).rowcount
            if not changed:
                raise NotFoundError("Affectation annuelle introuvable.")

    def options_for_year(self, school_year):
        self.ctx.session.require(self.read_perm)
        return self.repo.options_for_year(school_year)

    def validate(self, data):
        return {
            "employee_no": V.text(data, "employee_no", "N° employé", max_len=20, upper=True,
                                  pattern=V.CODE_RE),
            "first_name": V.text(data, "first_name", "Prénom", max_len=60, pattern=V.NAME_RE),
            "last_name": V.text(data, "last_name", "Nom", max_len=60, pattern=V.NAME_RE),
            "gender": V.choice(data, "gender", "Genre", ("M", "F")),
            "birth_date": V.date_iso(data, "birth_date", "Date de naissance"),
            "birth_place": V.text(data, "birth_place", "Lieu de naissance", required=False, max_len=100),
            "phone": V.text(data, "phone", "Téléphone", required=False, max_len=20, pattern=V.PHONE_RE),
            "address": V.text(data, "address", "Adresse", required=False, max_len=200),
            "position": V.text(data, "position", "Poste", required=False, max_len=80),
            "hire_date": V.date_iso(data, "hire_date", "Date d'embauche"),
        }


class ClassService(_OptionsMixin, CrudService):
    entity = "classes"
    repo_cls = ClassRepository
    read_perm, write_perm, delete_perm = "classes.read", "classes.write", "classes.delete"
    option_sql = "SELECT id, name AS label FROM classes ORDER BY name"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.school_year = school.current_school_year()

    def school_year_options(self):
        return used_school_years(self.db)

    def years_with_classes(self) -> list:
        """Années disposant réellement de classes : sert aux choix d'inscription/affectation."""
        return self.repo.years()

    def class_year_options(self):
        """Classes et années associées, pour éviter de demander une année séparément."""
        return [
            (f"{row['name']} - {row['school_year']}", row["id"], row["school_year"])
            for row in self.repo.class_year_options()
        ]

    def select_school_year(self, school_year):
        self.school_year = school_year or school.current_school_year()

    def page(self, search="", sort=None, desc=None, page=0, size=100):
        return self.page_for_year(self.school_year, search, sort, desc, page, size)

    def page_for_year(self, school_year, search="", sort=None, desc=None, page=0, size=100):
        self.ctx.session.require(self.read_perm)
        page = max(0, int(page))
        desc = self.default_desc if desc is None else desc
        rows = self.repo.page_for_year(school_year, search, sort, desc, size, page * size)
        total = self.repo.count_for_year(school_year, search)
        return Page(rows, total, page, size)

    def validate(self, data):
        school_year = V.school_year(data, "school_year")
        main_teacher_id = V.integer(data, "main_teacher_id", "Employé", minimum=1)
        if main_teacher_id is not None and not self.db.one(
                "SELECT 1 FROM employee_school_years "
                "WHERE employee_id=? AND school_year=?", (main_teacher_id, school_year)):
            raise ValidationError(
                "L'employé principal doit être affecté à la même année scolaire que la classe.")
        return {
            "name": V.text(data, "name", "Nom de la classe", max_len=40),
            "school_year": school_year,
            "capacity": V.integer(data, "capacity", "Effectif maximal", minimum=1, maximum=80) or 45,
            "main_teacher_id": main_teacher_id,
        }
