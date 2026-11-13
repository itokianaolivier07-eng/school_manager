"""Usage : python -m scripts.seed_demo [--students 30000]"""
import argparse
import random
import time
from datetime import date, timedelta

from app import config
from app.core import school
from app.database.connection import Database
from app.database.schema import migrate
from app.repositories.repos import ClassRepository, StudentRepository, TeacherRepository

FIRST = ["Itokiana", "Miora", "Hery", "Fanja", "Tahina", "Lova", "Safidy", "Nirina", "Aina", "Mamy",
         "Lucas", "Emma", "Léa", "Hugo", "Chloé", "Nathan", "Inès", "Louis", "Zoé", "Adam"]
LAST = ["Rakoto", "Randria", "Rasoa", "Andrianina", "Rabe", "Ravelo", "Razafy", "Martin", "Bernard",
        "Dubois", "Moreau", "Laurent", "Simon", "Michel", "Lefèvre", "Garcia", "Roux", "Fontaine"]
POSITIONS = ["Directeur", "Surveillant", "Comptable", "Secrétaire", "Enseignant", "Bibliothécaire",
             "Infirmier", "Gardien"]


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
        employees = []
        for i in range(1, 41):
            employees.append({
                "employee_no": f"E{i:04d}",
                "first_name": rnd.choice(FIRST),
                "last_name": rnd.choice(LAST),
                "gender": rnd.choice("MF"),
                "birth_date": (date(1975, 1, 1) + timedelta(days=rnd.randint(0, 10000))).isoformat(),
                "position": rnd.choice(POSITIONS),
                "hire_date": (date(2015, 1, 1) + timedelta(days=rnd.randint(0, 3000))).isoformat(),
            })
        TeacherRepository(db).bulk_insert(employees)
        sections = max(1, (n_students + school.DEFAULT_CAPACITY - 1) // school.DEFAULT_CAPACITY)
        classes = [{"name": f"Classe {section:03d}",
                    "school_year": school.current_school_year(), "capacity": 45,
                    "main_teacher_id": rnd.randint(1, 40)}
                   for section in range(1, sections + 1)]
        ClassRepository(db).bulk_insert(classes)
        students = []
        for i in range(1, n_students + 1):
            students.append({
                "matricule": f"E2026{i:06d}", "first_name": rnd.choice(FIRST), "last_name": rnd.choice(LAST),
                "birth_date": (date(2008, 1, 1) + timedelta(days=rnd.randint(0, 4000))).isoformat(),
                "gender": rnd.choice("MF"), "class_id": (i - 1) % len(classes) + 1, "status": "active"})
        StudentRepository(db).bulk_insert(students)
        salaries = [(eid, rnd.randint(300_000, 2_500_000)) for eid in range(1, 41)]
        db.executemany("INSERT INTO employee_salaries(employee_id, monthly_amount) VALUES (?,?)", salaries)
        today = date.today()
        attendance = []
        for day_offset in range(7):
            d = (today - timedelta(days=day_offset)).isoformat()
            for eid in range(1, 41):
                status = rnd.choices(["present", "late", "absent"], weights=[85, 10, 5])[0]
                if status == "absent":
                    attendance.append((eid, d, status, None, None))
                else:
                    arrival = f"{7 + rnd.randint(0, 1):02d}:{rnd.randint(0, 59):02d}"
                    departure = f"{16 + rnd.randint(0, 2):02d}:{rnd.randint(0, 59):02d}"
                    attendance.append((eid, d, status, arrival, departure))
        db.executemany(
            "INSERT INTO employee_attendance(employee_id, attendance_date, status, arrival_time, departure_time) "
            "VALUES (?,?,?,?,?)", attendance)
    print(f"{n_students} élèves, 40 employés, salaires et pointages insérés en {time.perf_counter() - t0:.1f}s")
    print("Lancez l'application : le premier démarrage vous demandera de créer l'administrateur.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--students", type=int, default=30000)
    main(ap.parse_args().students)
