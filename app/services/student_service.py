"""Élèves : CRUD + import/export CSV sécurisés (30 000+ lignes)."""
import csv
import os
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from app import config
from app.core import validators as V
from app.core import school
from app.core.exceptions import AppError, NotFoundError, ValidationError
from app.repositories.base import used_school_years
from app.repositories.repos import StudentRepository
from app.services.base import CrudService, Page, translate_integrity

EXPORT_COLS = ("matricule", "last_name", "first_name", "birth_date", "gender", "tutor_name",
               "tutor_phone", "tutor_profession", "father_name", "father_phone", "father_profession",
               "mother_name", "mother_phone", "mother_profession",
               "tuition_discount", "address", "class_name", "status")
STATUSES = ("active", "suspended", "graduated", "left")


@dataclass
class ImportReport:
    inserted: int = 0
    duplicates: int = 0
    errors: list = field(default_factory=list)   # (ligne, message)


_FORMULA_PREFIX = ("=", "@", "\t", "\r")
_NUMBERISH = re.compile(r"^[+-]?[\d][\d\s().\-]*$")


def csv_safe(value) -> str:
    """Neutralise l'injection de formules (Excel/LibreOffice) dans les exports,
    sans altérer les nombres et téléphones légitimes commençant par '+' ou '-'."""
    s = "" if value is None else str(value)
    head = s[:1]
    if head in _FORMULA_PREFIX:
        return "'" + s
    if head in ("+", "-") and not _NUMBERISH.match(s):
        return "'" + s
    return s


class StudentService(CrudService):
    entity = "students"
    repo_cls = StudentRepository
    read_perm, write_perm, delete_perm = "students.read", "students.write", "students.delete"

    def __init__(self, ctx):
        super().__init__(ctx)
        self.school_year = school.current_school_year()

    def school_year_options(self):
        return used_school_years(self.db)

    def select_school_year(self, school_year):
        self.school_year = school_year or school.current_school_year()

    def _class_year(self, class_id):
        row = self.db.one("SELECT school_year FROM classes WHERE id=?", (class_id,))
        return row["school_year"] if row else None

    def page(self, search="", sort=None, desc=None, page=0, size=config.PAGE_SIZE):
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
            row = self.repo.get(id_)
        if row is None:
            raise NotFoundError("Élément introuvable.")
        return dict(row)

    def validate(self, data):
        return {
            "matricule": V.text(data, "matricule", "Matricule", required=False, max_len=20,
                                upper=True, pattern=V.CODE_RE),
            "first_name": V.text(data, "first_name", "Prénom", max_len=60, pattern=V.NAME_RE),
            "last_name": V.text(data, "last_name", "Nom", max_len=60, pattern=V.NAME_RE),
            "birth_date": self._birth_date(data),
            "gender": V.choice(data, "gender", "Genre", ("M", "F"), required=False),
            "tutor_name": V.text(data, "tutor_name", "Tuteur", required=False, max_len=100),
            "tutor_phone": V.text(data, "tutor_phone", "Téléphone du tuteur", required=False,
                                  max_len=20, pattern=V.PHONE_RE),
            "tutor_profession": V.text(data, "tutor_profession", "Profession du tuteur",
                                       required=False, max_len=100),
            "father_name": V.text(data, "father_name", "Nom du père", required=False, max_len=100),
            "father_phone": V.text(data, "father_phone", "Téléphone du père", required=False,
                                   max_len=20, pattern=V.PHONE_RE),
            "father_profession": V.text(data, "father_profession", "Profession du père",
                                        required=False, max_len=100),
            "mother_name": V.text(data, "mother_name", "Nom de la mère", required=False, max_len=100),
            "mother_phone": V.text(data, "mother_phone", "Téléphone de la mère", required=False,
                                   max_len=20, pattern=V.PHONE_RE),
            "mother_profession": V.text(data, "mother_profession", "Profession de la mère",
                                        required=False, max_len=100),
            "tuition_discount": V.integer(data, "tuition_discount", "Remise", minimum=0, maximum=100) or 0,
            "address": V.text(data, "address", "Adresse", required=False, max_len=200),
            "class_id": V.integer(data, "class_id", "Classe", minimum=1),
            "status": V.choice(data, "status", "Statut", STATUSES, default="active"),
        }

    @staticmethod
    def _birth_date(data):
        d = V.date_iso(data, "birth_date", "Date de naissance")
        today = date.today()
        birth_date = date.fromisoformat(d)
        age = today.year - birth_date.year - (
            (today.month, today.day) < (birth_date.month, birth_date.day))
        if not school.MIN_AGE <= age <= school.MAX_AGE:
            raise ValidationError("Date de naissance : âge hors limites.")
        return d

    def _fill_matricules(self, rows):
        base = self.db.one("SELECT COALESCE(MAX(id),0) AS m FROM students")["m"]
        year = date.today().year
        for i, r in enumerate(rows, start=1):
            if not r.get("matricule"):
                r["matricule"] = f"E{year}{base + i:06d}"

    def prepare(self, clean):
        self._fill_matricules([clean])
        return clean

    def create(self, data) -> int:
        self.ctx.session.require(self.write_perm)
        clean = self.prepare(dict(self.validate(data)))
        class_id = clean.get("class_id")
        class_year = self._class_year(class_id) if class_id is not None else None
        if class_id is not None and class_year != self.school_year:
            raise ValidationError("La classe doit appartenir à l'année scolaire sélectionnée.")
        with self.db.transaction():
            try:
                student_id = self.repo.insert(clean)
                self.repo.enroll(student_id, class_id, self.school_year)
            except sqlite3.IntegrityError as e:
                raise translate_integrity(e) from e
        return student_id

    def update(self, id_, data) -> None:
        self.ctx.session.require(self.write_perm)
        clean = dict(self.validate(data))
        if not clean.get("matricule"):
            existing = self.db.one("SELECT matricule FROM students WHERE id=?", (id_,))
            if existing is None:
                raise NotFoundError("Élément introuvable.")
            clean["matricule"] = existing["matricule"]
        class_id = clean.get("class_id")
        class_year = self._class_year(class_id) if class_id is not None else None
        if class_id is not None and class_year != self.school_year:
            raise ValidationError("La classe doit appartenir à l'année scolaire sélectionnée.")
        enrollment_year = self.school_year
        with self.db.transaction():
            try:
                if not self.repo.update(id_, clean):
                    raise NotFoundError("Élément introuvable.")
                self.db.execute(
                    "INSERT INTO student_enrollments(student_id, school_year, class_id) "
                    "VALUES(?,?,?) ON CONFLICT(student_id, school_year) "
                    "DO UPDATE SET class_id=excluded.class_id",
                    (id_, enrollment_year, class_id))
            except sqlite3.IntegrityError as e:
                raise translate_integrity(e) from e

    def enroll_existing(self, student_id, class_id, school_year):
        self.ctx.session.require(self.write_perm)
        school_year = V.school_year({"school_year": school_year}, "school_year")
        if self._class_year(class_id) != school_year:
            raise ValidationError("La classe doit appartenir à l’année scolaire sélectionnée.")
        with self.db.transaction():
            if self.db.one("SELECT id FROM students WHERE id=?", (student_id,)) is None:
                raise NotFoundError("Élève introuvable.")
            try:
                self.repo.enroll(student_id, class_id, school_year)
            except sqlite3.IntegrityError as e:
                raise translate_integrity(e) from e

    def unenroll(self, student_id, school_year):
        self.ctx.session.require(self.write_perm)
        school_year = V.school_year({"school_year": school_year}, "school_year")
        with self.db.transaction():
            if self.db.one(
                    "SELECT id FROM payments WHERE student_id=? AND school_year=? LIMIT 1",
                    (student_id, school_year)):
                raise ValidationError(
                    "L'élève a des paiements pour cette année; son inscription doit être conservée.")
            changed = self.db.execute(
                "DELETE FROM student_enrollments WHERE student_id=? AND school_year=?",
                (student_id, school_year)).rowcount
            if not changed:
                raise NotFoundError("Inscription annuelle introuvable.")

    # --- Import / export ---
    def import_csv(self, path) -> ImportReport:
        self.ctx.session.require("students.import")
        p = Path(path)
        if p.stat().st_size > config.MAX_IMPORT_BYTES:
            raise ValidationError("Fichier trop volumineux (25 Mo maximum).")
        classes = {r["name"].upper(): r["id"] for r in self.db.all(
            "SELECT id, name FROM classes WHERE school_year=?", (self.school_year,))}
        report, batch = ImportReport(), []

        def flush():
            if not batch:
                return
            self._fill_matricules(batch)
            n = self.repo.bulk_insert(batch, or_ignore=True)
            for row in batch:
                student = self.db.one(
                    "SELECT id FROM students WHERE matricule=?", (row["matricule"],))
                if student:
                    self.db.execute(
                        "INSERT OR IGNORE INTO student_enrollments"
                        "(student_id, school_year, class_id) VALUES(?,?,?)",
                        (student["id"], self.school_year, row.get("class_id")))
            report.inserted += n
            report.duplicates += len(batch) - n
            batch.clear()

        with open(p, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            missing = {"first_name", "last_name", "birth_date"} - set(reader.fieldnames or [])
            if missing:
                raise ValidationError("Colonnes manquantes : " + ", ".join(sorted(missing)))
            with self.db.transaction():
                for line, row in enumerate(reader, start=2):
                    try:
                        row = dict(row)
                        if "tutor_name" not in row and "guardian_name" in row:
                            row["tutor_name"] = row["guardian_name"]
                        cname = (row.pop("class", "") or "").strip().upper()
                        if cname:
                            if cname not in classes:
                                raise ValidationError(f"Classe inconnue : {cname}")
                            row["class_id"] = classes[cname]
                        batch.append(self.validate(row))
                    except AppError as e:
                        if len(report.errors) < 200:
                            report.errors.append((line, str(e)))
                    if len(batch) >= 1000:
                        flush()
                flush()
        return report

    def export_csv(self, path, search="") -> int:
        self.ctx.session.require("students.export")
        where, params = self.repo._where(search)
        conditions = [where[7:]] if where else []
        conditions.append("e.school_year=?")
        sql = (f"{self.repo._select()} WHERE {' AND '.join(conditions)} "
               "ORDER BY t.last_name, t.first_name, t.id")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        n = 0
        with os.fdopen(fd, "w", newline="", encoding="utf-8-sig") as f:
            os.fchmod(f.fileno(), 0o600)
            w = csv.writer(f)
            w.writerow(EXPORT_COLS)
            cur = self.db.conn.execute(sql, [*params, self.school_year])
            while True:
                rows = cur.fetchmany(1000)
                if not rows:
                    break
                for r in rows:
                    w.writerow([csv_safe(r[c]) for c in EXPORT_COLS])
                n += len(rows)
        return n
