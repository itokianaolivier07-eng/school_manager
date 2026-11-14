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
POSITIONS = ["Directrice", "Surveillante", "Comptable", "Secrétaire", "Professeur",
             "Éducatrice", "Éducateur", "Infirmière", "Gardien"]


def _birth_date_for_level(level: str, today: date, rnd: random.Random) -> str:
    minimum, maximum = school.LEVEL_AGE_RANGES[level]

    def subtract_years(years):
        try:
            return today.replace(year=today.year - years)
        except ValueError:
            return today.replace(year=today.year - years, month=2, day=28)

    youngest = subtract_years(minimum)
    oldest = subtract_years(maximum + 1) + timedelta(days=1)
    return (oldest + timedelta(days=rnd.randrange((youngest - oldest).days + 1))).isoformat()


def main(n_students: int) -> None:
    if n_students < 1:
        raise ValueError("Le nombre d'élèves doit être supérieur à zéro.")
    config.ensure_dirs()
    db = Database(config.DB_PATH)
    try:
        migrate(db)
        occupied = any(db.one(f"SELECT EXISTS(SELECT 1 FROM {table})")[0]
                       for table in ("students", "teachers", "classes"))
        if occupied:
            print("La base contient déjà des données scolaires : abandon.")
            return
        rnd = random.Random(42)
        t0 = time.perf_counter()
        today = date.today()
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
            section_count = max(
                len(school.SCHOOL_LEVELS),
                (n_students + school.DEFAULT_CAPACITY - 1) // school.DEFAULT_CAPACITY)
            classes = []
            for section in range(section_count):
                level = school.SCHOOL_LEVELS[section % len(school.SCHOOL_LEVELS)]
                section_no = section // len(school.SCHOOL_LEVELS) + 1
                classes.append({
                    "name": f"{level}-{section_no:02d}",
                    "school_year": school.current_school_year(),
                    "capacity": school.DEFAULT_CAPACITY,
                    "main_teacher_id": rnd.randint(1, 40),
                })
            ClassRepository(db).bulk_insert(classes)
            students = []
            for i in range(1, n_students + 1):
                school_class = classes[(i - 1) % len(classes)]
                level = school_class["name"].rsplit("-", 1)[0]
                students.append({
                    "matricule": f"E{today.year}{i:06d}",
                    "first_name": rnd.choice(FIRST),
                    "last_name": rnd.choice(LAST),
                    "birth_date": _birth_date_for_level(level, today, rnd),
                    "gender": rnd.choice("MF"),
                    "class_id": (i - 1) % len(classes) + 1,
                    "status": "active",
                })
            StudentRepository(db).bulk_insert(students)
            salaries = []
            for employee_id, employee in enumerate(employees, start=1):
                if "prof" in employee["position"].casefold():
                    salaries.append((employee_id, 0, "hourly", rnd.randint(15_000, 30_000)))
                else:
                    salaries.append((employee_id, rnd.randint(300_000, 2_500_000), "monthly", 0))
            db.executemany(
                "INSERT INTO employee_salaries(employee_id, monthly_amount, pay_type, hourly_rate) "
                "VALUES (?,?,?,?)", salaries)
            attendance = []
            for day_offset in range(7):
                attendance_date = (today - timedelta(days=day_offset)).isoformat()
                for employee_id in range(1, 41):
                    status = rnd.choices(["present", "late", "absent"], weights=[85, 10, 5])[0]
                    if status == "absent":
                        attendance.append((employee_id, attendance_date, status, None, None))
                    else:
                        arrival = f"{7 + rnd.randint(0, 1):02d}:{rnd.randint(0, 59):02d}"
                        departure = f"{16 + rnd.randint(0, 2):02d}:{rnd.randint(0, 59):02d}"
                        attendance.append(
                            (employee_id, attendance_date, status, arrival, departure))
            db.executemany(
                "INSERT INTO employee_attendance(employee_id, attendance_date, status, arrival_time, "
                "departure_time) VALUES (?,?,?,?,?)", attendance)
        print(f"{n_students} élèves répartis par niveau, 40 employés, salaires et pointages "
              f"insérés en {time.perf_counter() - t0:.1f}s")
        print("Lancez l'application : le premier démarrage vous demandera de créer l'administrateur.")
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--students", type=int, default=30000)
    main(ap.parse_args().students)
