"""Élèves : CRUD + import/export CSV sécurisés (30 000+ lignes)."""
import csv
import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from app import config
from app.core import validators as V
from app.core import school
from app.core.exceptions import AppError, ValidationError
from app.repositories.repos import StudentRepository
from app.services.base import CrudService

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


def csv_safe(value) -> str:
    """Empêche l'injection de formules (Excel/LibreOffice) dans les exports."""
    s = "" if value is None else str(value)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


class StudentService(CrudService):
    entity = "students"
    repo_cls = StudentRepository
    read_perm, write_perm, delete_perm = "students.read", "students.write", "students.delete"

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

    # --- Import / export ---
    def import_csv(self, path) -> ImportReport:
        self.ctx.session.require("students.import")
        p = Path(path)
        if p.stat().st_size > config.MAX_IMPORT_BYTES:
            raise ValidationError("Fichier trop volumineux (25 Mo maximum).")
        classes = {r["name"].upper(): r["id"] for r in self.db.all("SELECT id, name FROM classes")}
        report, batch = ImportReport(), []

        def flush():
            if not batch:
                return
            self._fill_matricules(batch)
            n = self.repo.bulk_insert(batch, or_ignore=True)
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
                self.log("import_csv", None, f"{report.inserted} ajoutés, {report.duplicates} doublons, "
                                              f"{len(report.errors)} erreurs")
        return report

    def export_csv(self, path, search="") -> int:
        self.ctx.session.require("students.export")
        where, params = self.repo._where(search)
        sql = f"{self.repo._select()}{where} ORDER BY t.last_name, t.first_name, t.id"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        n = 0
        with os.fdopen(fd, "w", newline="", encoding="utf-8-sig") as f:
            os.fchmod(f.fileno(), 0o600)
            w = csv.writer(f)
            w.writerow(EXPORT_COLS)
            cur = self.db.conn.execute(sql, params)
            while True:
                rows = cur.fetchmany(1000)
                if not rows:
                    break
                for r in rows:
                    w.writerow([csv_safe(r[c]) for c in EXPORT_COLS])
                n += len(rows)
        self.log("export_csv", None, f"{n} lignes")
        return n
