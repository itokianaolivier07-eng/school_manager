"""Génère des données de démonstration (30 000 élèves par défaut) pour tester les performances.

Usage : python -m scripts.seed_demo [--students 30000]
"""
import argparse
import random
import time
from datetime import date, timedelta

from app import config
from app.core import school
from app.database.connection import Database
from app.database.schema import migrate
from app.repositories.repos import ClassRepository, StudentRepository, SubjectRepository, TeacherRepository

FIRST = ["Itokiana", "Miora", "Hery", "Fanja", "Tahina", "Lova", "Safidy", "Nirina", "Aina", "Mamy",
         "Lucas", "Emma", "Léa", "Hugo", "Chloé", "Nathan", "Inès", "Louis", "Zoé", "Adam"]
LAST = ["Rakoto", "Randria", "Rasoa", "Andrianina", "Rabe", "Ravelo", "Razafy", "Martin", "Bernard",
        "Dubois", "Moreau", "Laurent", "Simon", "Michel", "Lefèvre", "Garcia", "Roux", "Fontaine"]
SUBJECTS = [("MATH", "Mathématiques", 4), ("FR", "Français", 4), ("ANG", "Anglais", 2),
            ("HG", "Histoire-Géographie", 2), ("SVT", "Sciences de la vie", 2),
            ("PHY", "Physique-Chimie", 3), ("INFO", "Informatique", 2), ("EPS", "Sport", 1)]


def main(n_students: int) -> None:
    config.ensure_dirs()
    db = Database(config.DB_PATH)
    migrate(db)
    if db.one("SELECT COUNT(*) AS n FROM students")["n"]:
        print("La base contient déjà des élèves : abandon.")
        return
    rnd = random.Random(42)
    t0 = time.perf_counter()
    with db.transaction():
        teachers = [{"employee_no": f"P{i:04d}", "first_name": rnd.choice(FIRST),
                     "last_name": rnd.choice(LAST), "email": f"prof{i}@ecole.test"} for i in range(1, 41)]
        TeacherRepository(db).bulk_insert(teachers)
        sections = max(1, (n_students + len(school.LEVELS) * 45 - 1) // (len(school.LEVELS) * 45))
        classes = [{"name": f"{lvl}-{section:03d}", "level": lvl,
                    "school_year": school.current_school_year(), "capacity": 45,
                    "main_teacher_id": rnd.randint(1, 40)}
                   for lvl in school.LEVELS for section in range(1, sections + 1)]
        ClassRepository(db).bulk_insert(classes)
        SubjectRepository(db).bulk_insert([{"code": c, "name": n, "coefficient": k,
                                            "teacher_id": rnd.randint(1, 40)} for c, n, k in SUBJECTS])
        students = []
        for i in range(1, n_students + 1):
            students.append({
                "matricule": f"E2026{i:06d}", "first_name": rnd.choice(FIRST), "last_name": rnd.choice(LAST),
                "birth_date": (date(2008, 1, 1) + timedelta(days=rnd.randint(0, 4000))).isoformat(),
                "gender": rnd.choice("MF"), "class_id": (i - 1) % len(classes) + 1, "status": "active"})
        StudentRepository(db).bulk_insert(students)
        grades = [(sid, sub, 1, round(rnd.uniform(4, 20), 2))
                  for sid in range(1, n_students + 1) for sub in range(1, len(SUBJECTS) + 1)]
        db.executemany("INSERT INTO grades(student_id, subject_id, term, value) VALUES (?,?,?,?)", grades)
    print(f"{n_students} élèves, {len(grades)} notes insérés en {time.perf_counter() - t0:.1f}s")
    print("Lancez l'application : le premier démarrage vous demandera de créer l'administrateur.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--students", type=int, default=30000)
    main(ap.parse_args().students)
