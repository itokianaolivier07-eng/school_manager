"""Usage : python -m scripts.seed_demo [--students 280] [--replace-demo]"""
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
PROFESSIONS = ["Agriculteur", "Commerçant", "Enseignant", "Fonctionnaire", "Infirmier",
               "Ménagère", "Médecin", "Ouvrier", "Artisan", "Sans emploi"]


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


def main(n_students: int, replace_demo: bool = False) -> None:
    if n_students < 1:
        raise ValueError("Le nombre d'élèves doit être supérieur à zéro.")
    max_students = len(school.SCHOOL_LEVELS) * school.DEFAULT_CAPACITY
    if n_students > max_students:
        raise ValueError(f"Le nombre d'élèves ne peut pas dépasser {max_students} "
                         "avec une seule classe par niveau.")
    config.ensure_dirs()
    db = Database(config.DB_PATH)
    try:
        migrate(db)
        occupied = any(db.one(f"SELECT EXISTS(SELECT 1 FROM {table})")[0]
                       for table in ("students", "teachers", "classes"))
        if occupied:
            if not replace_demo:
                print("La base contient déjà des données scolaires : abandon.")
                return
            if db.one("SELECT EXISTS(SELECT 1 FROM payments)")[0]:
                raise ValueError("La base contient des paiements; remplacement refusé pour préserver "
                                 "les données comptables.")
            with db.transaction():
                db.execute("DELETE FROM class_tuition_fees")
                db.execute("DELETE FROM students")
                db.execute("DELETE FROM classes")
                db.execute("DELETE FROM salary_disbursements")
                db.execute("DELETE FROM teachers")
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
            db.executemany(
                "INSERT INTO employee_school_years(employee_id, school_year) VALUES(?,?)",
                [(i, school.current_school_year()) for i in range(1, len(employees) + 1)])
            classes = []
            for level in school.SCHOOL_LEVELS:
                classes.append({
                    "name": level,
                    "school_year": school.current_school_year(),
                    "capacity": school.DEFAULT_CAPACITY,
                    "main_teacher_id": rnd.randint(1, 40),
                })
            ClassRepository(db).bulk_insert(classes)
            students = []
            for i in range(1, n_students + 1):
                class_index = (i - 1) % len(classes)
                level = classes[class_index]["name"]
                students.append({
                    "matricule": f"E{today.year}{i:06d}",
                    "first_name": rnd.choice(FIRST),
                    "last_name": rnd.choice(LAST),
                    "birth_date": _birth_date_for_level(level, today, rnd),
                    "gender": rnd.choice("MF"),
                    "class_id": class_index + 1,
                    "status": "active",
                    "tutor_profession": rnd.choice(PROFESSIONS),
                    "father_profession": rnd.choice(PROFESSIONS),
                    "mother_profession": rnd.choice(PROFESSIONS),
                })
            StudentRepository(db).bulk_insert(students)
            db.execute(
                "INSERT INTO student_enrollments(student_id, school_year, class_id) "
                "SELECT s.id, c.school_year, s.class_id FROM students s "
                "JOIN classes c ON c.id=s.class_id")
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
    ap.add_argument("--students", type=int, default=280)
    ap.add_argument("--replace-demo", action="store_true",
                    help="remplacer les données scolaires de démonstration existantes")
    args = ap.parse_args()
    main(args.students, replace_demo=args.replace_demo)
