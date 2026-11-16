import os
import sqlite3
import stat
import time
from datetime import date

import pytest

from app import config
from app.core import school
from app.core.exceptions import AuthenticationError, DuplicateError, PermissionDenied, ValidationError
from app.database.connection import Database
from app.database.schema import MIGRATION_1, MIGRATIONS, migrate
from tests.conftest import make_env

VALID = {"first_name": "Miora", "last_name": "Rakoto", "birth_date": "2010-05-12"}


def test_create_student_autogenerates_matricule(env):
    ctx, svc = env
    sid = svc.students.create(VALID)
    row = svc.students.get(sid)
    assert row["matricule"].startswith("E") and row["status"] == "active"


def test_student_minimum_age_allows_four_months_but_not_three(env, monkeypatch):
    _, svc = env

    class FrozenDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 11, 16)

    monkeypatch.setattr("app.services.student_service.date", FrozenDate)
    monkeypatch.setattr("app.core.validators.date", FrozenDate)

    assert svc.students.validate({**VALID, "birth_date": "2026-07-16"})["birth_date"] == "2026-07-16"
    with pytest.raises(ValidationError, match="âge hors limites"):
        svc.students.validate({**VALID, "birth_date": "2026-08-16"})


def test_student_schema_and_legacy_contact_privacy(env):
    ctx, svc = env
    assert ctx.db.one("PRAGMA user_version")[0] == 15
    class_columns = {row["name"] for row in ctx.db.all("PRAGMA table_info(classes)")}
    assert "level" not in class_columns
    assert ctx.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name='tuition_fees'") is None
    columns = {row["name"] for row in ctx.db.all("PRAGMA table_info(students)")}
    assert {"guardian_name", "tutor_name", "father_name", "mother_name",
            "tutor_phone", "father_phone", "mother_phone",
            "tutor_profession", "father_profession", "mother_profession",
            "tuition_discount", "email", "phone"} <= columns

    student_id = svc.students.create({**VALID, "email": "ancien@example.test"})
    assert "email" not in svc.students.get(student_id)
    assert "phone" not in svc.students.get(student_id)

    with pytest.raises(sqlite3.IntegrityError):
        ctx.db.execute(
            "UPDATE students SET tutor_profession=? WHERE id=?",
            ("x" * 101, student_id))


def test_school_year_options_come_only_from_classes(env):
    ctx, svc = env
    years = ("2025-2026", "2026-2027")
    for year in years:
        svc.classes.create({"name": f"Classe {year[:4]}", "school_year": year})
    ctx.db.execute(
        "INSERT INTO expenses (category, label, amount, expense_date) "
        "VALUES ('loyer', 'Charge historique', 1000, '2028-01-01')")

    assert svc.classes.school_year_options() == ["2026-2027", "2025-2026"]
    assert svc.students.school_year_options() == ["2026-2027", "2025-2026"]
    assert svc.teachers.school_year_options() == ["2026-2027", "2025-2026"]
    assert svc.dashboard.finance_year_options() == ["2026-2027", "2025-2026"]
    assert svc.classes.class_year_options() == [
        ("Classe 2026 - 2026-2027", 2, "2026-2027"),
        ("Classe 2025 - 2025-2026", 1, "2025-2026"),
    ]


def test_migration_from_existing_database_preserves_student_data():
    db = Database()
    try:
        db.conn.executescript(f"{MIGRATION_1}\nPRAGMA user_version=1;")
        db.execute(
            "INSERT INTO students (matricule, first_name, last_name, birth_date, email, phone) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("E1", "Miora", "Rakoto", "2010-05-12", "ancien@example.test", "12345678"))
        db.execute(
            "INSERT INTO teachers (employee_no, first_name, last_name, speciality) "
            "VALUES (?, ?, ?, ?)",
            ("ENS001", "Aina", "Rakoto", "Enseignante"))

        migrate(db)

        row = db.one("SELECT email, phone, guardian_name, tutor_name, father_name, mother_name, "
                     "tutor_phone, father_phone, mother_phone, "
                     "tutor_profession, father_profession, mother_profession, "
                     "tuition_discount FROM students WHERE matricule='E1'")
        assert tuple(row) == (
            "ancien@example.test", "12345678", None, None, None, None, None, None, None,
            None, None, None, 0)
        teacher = db.one("SELECT position FROM teachers WHERE employee_no='ENS001'")
        assert teacher["position"] == "Enseignante"
        assert db.one("PRAGMA user_version")[0] == 15
        class_columns = {row["name"] for row in db.all("PRAGMA table_info(classes)")}
        assert "level" not in class_columns
    finally:
        db.close()


def test_salary_migration_preserves_existing_monthly_rates():
    db = Database()
    try:
        for version, sql in MIGRATIONS:
            if version == 10:
                break
            db.conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version={version};\nCOMMIT;")
        db.execute(
            "INSERT INTO teachers (employee_no, first_name, last_name, speciality) "
            "VALUES ('ENS001', 'Aina', 'Rakoto', 'Maîtresse')")
        db.execute("INSERT INTO employee_salaries (employee_id, monthly_amount) VALUES (1, 350000)")

        migrate(db)

        salary = db.one(
            "SELECT monthly_amount, pay_type, hourly_rate FROM employee_salaries WHERE employee_id=1")
        assert tuple(salary) == (350000, "monthly", 0)
        assert db.one("PRAGMA user_version")[0] == 15
    finally:
        db.close()


def test_arrears_index_migration_from_existing_database():
    db = Database()
    try:
        for version, sql in MIGRATIONS:
            if version == 11:
                break
            db.conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version={version};\nCOMMIT;")

        assert db.one("PRAGMA user_version")[0] == 10
        migrate(db)

        assert db.one("PRAGMA user_version")[0] == 15
        assert db.one(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_payments_arrears'")
    finally:
        db.close()


def test_validation_rejects_bad_input(env):
    _, svc = env
    for bad in ({**VALID, "first_name": "<script>"}, {**VALID, "birth_date": "2999-01-01"},
                {**VALID, "birth_date": "1900-01-01"}, {**VALID, "gender": "X"}):
        with pytest.raises(ValidationError):
            svc.students.create(bad)


def test_pagination_rejects_invalid_or_unbounded_sizes(env):
    _, svc = env
    for page, size in ((0, 0), (0, -1), (0, 1001), (-1, 100), ("invalid", 100),
                       (None, 100)):
        with pytest.raises(ValidationError):
            svc.students.page(page=page, size=size)
    with pytest.raises(ValidationError):
        svc.expenses.page(page=0, size=0)
    with pytest.raises(ValidationError):
        svc.payments.history_page(class_id="1; DROP TABLE students")


def test_transaction_preserves_original_error_if_transaction_was_closed(env):
    ctx, _ = env
    with pytest.raises(RuntimeError, match="original failure"):
        with ctx.db.transaction():
            ctx.db.execute("COMMIT")
            raise RuntimeError("original failure")


def test_class_without_level_and_optional_parent_names(env):
    _, svc = env
    class_id = svc.classes.create({"name": "Classe A", "school_year": "2026-2027"})
    class_row = svc.classes.get(class_id)
    assert "level" not in class_row
    student_id = svc.students.create({**VALID, "class_id": class_id})
    student = svc.students.get(student_id)
    assert (student["tutor_name"], student["father_name"], student["mother_name"]) == (None, None, None)

    svc.students.update(student_id, {**VALID, "matricule": student["matricule"], "class_id": class_id,
                                     "tutor_name": "Tuteur", "father_name": "Père", "mother_name": "Mère",
                                     "tutor_phone": "+261 34 12 345 67", "father_phone": "0341234567",
                                     "mother_phone": "0321234567", "tutor_profession": "Enseignant",
                                     "father_profession": "Agriculteur", "mother_profession": "Commerçante"})
    student = svc.students.get(student_id)
    assert (student["tutor_name"], student["father_name"], student["mother_name"]) == (
        "Tuteur", "Père", "Mère")
    assert (student["tutor_phone"], student["father_phone"], student["mother_phone"]) == (
        "+261 34 12 345 67", "0341234567", "0321234567")
    assert (student["tutor_profession"], student["father_profession"], student["mother_profession"]) == (
        "Enseignant", "Agriculteur", "Commerçante")


def test_student_employee_and_class_history_filters(env):
    _, svc = env
    year_one, year_two = "2025-2026", "2026-2027"
    class_one = svc.classes.create({"name": "CP", "school_year": year_one})
    class_two = svc.classes.create({"name": "CP", "school_year": year_two})
    svc.students.select_school_year(year_one)
    student_id = svc.students.create({**VALID, "class_id": class_one})
    svc.students.select_school_year(year_two)
    svc.students.enroll_existing(student_id, class_two, year_two)
    assert svc.students.page().total == 1
    assert svc.students.get(student_id)["class_name"] == "CP"
    svc.students.select_school_year(year_one)
    assert svc.students.page().total == 1
    assert svc.students.get(student_id)["school_year"] == year_one

    employee_id = svc.teachers.create({
        "employee_no": "ENSYEAR", "first_name": "Aina", "last_name": "Rabe",
        "gender": "F", "birth_date": "1985-01-01", "hire_date": "2020-09-01",
    })
    svc.teachers.assign_year(employee_id, year_one)
    svc.teachers.select_school_year(year_one)
    assert svc.teachers.page().total == 1
    svc.teachers.select_school_year(year_two)
    assert svc.teachers.page().total == 1

    assert svc.classes.page_for_year(year_one).total == 1
    assert svc.classes.page_for_year(year_two).total == 1


def test_student_and_class_references_must_match_school_year(env):
    _, svc = env
    current_year = school.current_school_year()
    next_start = int(current_year[:4]) + 1
    other_year = f"{next_start}-{next_start + 1}"
    class_id = svc.classes.create({"name": "CP", "school_year": other_year})
    with pytest.raises(ValidationError, match="année scolaire sélectionnée"):
        svc.students.create({**VALID, "class_id": class_id})

    employee_id = svc.teachers.create({
        "employee_no": "ENSANNUAL", "first_name": "Aina", "last_name": "Rabe",
        "gender": "F", "birth_date": "1985-01-01", "hire_date": "2020-09-01",
    })
    with pytest.raises(ValidationError, match="même année scolaire"):
        svc.classes.create({
            "name": "CE1", "school_year": other_year, "main_teacher_id": employee_id,
        })
    svc.teachers.assign_year(employee_id, other_year)
    class_with_teacher = svc.classes.create({
        "name": "CE1", "school_year": other_year, "main_teacher_id": employee_id,
    })
    assert svc.classes.get(class_with_teacher)["main_teacher_id"] == employee_id


def test_student_parent_phone_validation(env):
    _, svc = env
    with pytest.raises(ValidationError, match="Téléphone du père"):
        svc.students.create({**VALID, "father_phone": "not a phone"})


def test_teacher_profile_fields(env):
    _, svc = env
    teacher_id = svc.teachers.create({
        "employee_no": "ENS001",
        "last_name": "Rakoto",
        "first_name": "Aina Miora",
        "gender": "F",
        "birth_date": "1985-04-12",
        "birth_place": "Antananarivo",
        "phone": "0341234567",
        "address": "Analamahitsy",
        "position": "Enseignante",
        "hire_date": "2020-09-01",
    })
    teacher = svc.teachers.get(teacher_id)
    assert tuple(teacher[key] for key in (
        "employee_no", "last_name", "first_name", "gender", "birth_date", "birth_place",
        "phone", "address", "position", "hire_date"
    )) == ("ENS001", "Rakoto", "Aina Miora", "F", "1985-04-12", "Antananarivo",
           "0341234567", "Analamahitsy", "Enseignante", "2020-09-01")

    with pytest.raises(ValidationError):
        svc.teachers.create({"employee_no": "ENS002", "last_name": "Rabe", "first_name": "Soa",
                             "birth_date": "1986-04-12", "hire_date": "2020-09-01"})


def test_teacher_hourly_and_monthly_salary_disbursements(env):
    _, svc = env
    professor_id = svc.teachers.create({
        "employee_no": "PROF001", "first_name": "Mamy", "last_name": "Rabe",
        "gender": "M", "birth_date": "1980-01-01", "hire_date": "2010-01-01",
        "position": "Professeur",
    })
    teacher_id = svc.teachers.create({
        "employee_no": "ENS001", "first_name": "Aina", "last_name": "Rakoto",
        "gender": "F", "birth_date": "1985-01-01", "hire_date": "2010-01-01",
        "position": "Maîtresse",
    })
    professor_salary = svc.salaries.create({
        "employee_id": professor_id, "pay_type": "monthly", "hourly_rate": 25000})
    teacher_salary = svc.salaries.create({"employee_id": teacher_id, "monthly_amount": 400000})
    professor = svc.salaries.get(professor_salary)
    teacher = svc.salaries.get(teacher_salary)
    assert (professor["pay_type"], professor["hourly_rate"]) == ("hourly", 25000)
    assert professor["monthly_amount"] == 0
    assert (teacher["pay_type"], teacher["monthly_amount"]) == ("monthly", 400000)

    payout_id = svc.salary_disbursements.record({
        "employee_id": professor_id, "title": "Indemnité horaire",
        "payout_date": "2026-09-15", "hours": 3.5,
    })
    payout = svc.salary_disbursements.get(payout_id)
    assert (payout["hours"], payout["hourly_rate"], payout["amount"]) == (3.5, 25000, 87500)
    assert payout["school_year"] == "2026-2027"
    assert payout["employee_no"] == "PROF001"
    assert payout["position"] == "Professeur"

    monthly_payout_id = svc.salary_disbursements.record({
        "employee_id": teacher_id, "title": "Avance",
        "payout_date": "2026-08-15", "amount": 100000,
    })
    monthly_payout = svc.salary_disbursements.get(monthly_payout_id)
    assert monthly_payout["school_year"] == "2025-2026"
    assert monthly_payout["amount"] == 100000
    assert monthly_payout["hours"] is None

    with pytest.raises(ValidationError):
        svc.salary_disbursements.record({
            "employee_id": professor_id, "title": "Salaire",
            "payout_date": "2026-09-15", "hours": 0,
        })


def test_duplicate_matricule(env):
    _, svc = env
    svc.students.create({**VALID, "matricule": "ABC123"})
    with pytest.raises(DuplicateError):
        svc.students.create({**VALID, "matricule": "abc123"})


def test_sql_injection_is_inert(env):
    ctx, svc = env
    svc.students.create(VALID)
    page = svc.students.page(search="'; DROP TABLE students;--", sort="id; DROP TABLE students")
    assert page.total == 0
    assert svc.students.page(search="' OR 1=1 --").total == 0
    assert svc.students.page().total == 1


def test_30000_students_pagination_and_search(env):
    ctx, svc = env
    class_id = svc.classes.create({
        "name": "CP", "school_year": school.current_school_year(),
    })
    rows = [{"matricule": f"E{i:07d}", "first_name": "Jean", "last_name": f"Nom{i % 500:03d}",
             "birth_date": "2010-01-01", "status": "active", "class_id": class_id}
            for i in range(30000)]
    with ctx.db.transaction():
        svc.students.repo.bulk_insert(rows)
        ctx.db.execute(
            "INSERT INTO student_enrollments(student_id,school_year,class_id) "
            "SELECT id,?,? FROM students", (school.current_school_year(), class_id))
    t = time.perf_counter()
    p = svc.students.page(page=150, sort="last_name")
    s = svc.students.page(search="Nom042")
    elapsed = time.perf_counter() - t
    assert p.total == 30000 and len(p.rows) == config.PAGE_SIZE and p.pages == 300
    assert s.total == 60
    assert elapsed < 1.0, f"trop lent : {elapsed:.2f}s"


def test_audit_log_records_actions_and_is_immutable(env):
    ctx, svc = env
    expense_id = svc.expenses.create({"category": "eau", "amount": 1000, "expense_date": "2026-09-05"})
    svc.expenses.delete(expense_id)
    svc.users.create({"username": "marie", "full_name": "Marie", "role": "secretary",
                      "password": "Str0ng!Passw0rd2"})
    rows = ctx.db.all("SELECT action, entity, username, detail FROM audit_log ORDER BY id")
    assert [(r["action"], r["entity"]) for r in rows] == [
        ("create", "expenses"), ("delete", "expenses"), ("create", "users")]
    assert all(r["username"] == "admin" for r in rows)
    assert all("password" not in (r["detail"] or "") for r in rows)
    with pytest.raises(sqlite3.IntegrityError):
        ctx.db.execute("DELETE FROM audit_log")
    with pytest.raises(sqlite3.IntegrityError):
        ctx.db.execute("UPDATE audit_log SET action='x'")


def test_lockout_after_failed_logins(env):
    ctx, svc = env
    ctx.session.logout()
    for _ in range(config.MAX_FAILED_LOGINS):
        with pytest.raises(AuthenticationError):
            svc.auth.login("admin", "mauvais")
    with pytest.raises(AuthenticationError, match="verrouillé"):
        svc.auth.login("admin", "Str0ng!Passw0rd")


def test_login_ok_and_unknown_user_same_message(env):
    ctx, svc = env
    ctx.session.logout()
    with pytest.raises(AuthenticationError) as e1:
        svc.auth.login("inconnu", "x")
    with pytest.raises(AuthenticationError) as e2:
        svc.auth.login("admin", "x")
    assert str(e1.value) == str(e2.value)
    assert svc.auth.login("admin", "Str0ng!Passw0rd").role == "admin"


def test_cannot_remove_last_admin_or_self(env):
    ctx, svc = env
    me = ctx.session.user.id
    with pytest.raises(ValidationError):
        svc.users.delete(me)
    with pytest.raises(ValidationError):
        svc.users.update(me, {"username": "admin", "full_name": "A", "role": "teacher", "is_active": 1})


def test_search_works_on_joined_columns(env):
    _, svc = env
    class_id = svc.classes.create({"name": "CP", "school_year": "2026-2027"})
    svc.fees.create({"class_id": class_id, "monthly_amount": 1000})
    employee_id = svc.teachers.create({
        "employee_no": "ENS001", "first_name": "Aina", "last_name": "Rakoto",
        "gender": "F", "birth_date": "1985-01-01", "hire_date": "2020-09-01"})
    svc.attendance.create({"employee_id": employee_id, "attendance_date": "2026-11-10",
                           "status": "present", "arrival_time": "08:00", "departure_time": "17:00"})
    svc.salaries.create({"employee_id": employee_id, "monthly_amount": 400000})

    assert svc.attendance.page(search="Rak").total == 1
    assert svc.salaries.page(search="Rak").total == 1
    assert svc.fees.page(search="CP").total == 1
    assert svc.attendance.page(search="introuvable").total == 0


def test_self_demotion_updates_own_session(env):
    ctx, svc = env
    me = ctx.session.user.id
    svc.users.create({"username": "admin2", "full_name": "Admin 2", "role": "admin",
                      "is_active": 1, "password": "Str0ng!Passw0rd"})
    svc.users.update(me, {"username": "admin", "full_name": "Admin", "role": "secretary",
                          "is_active": 1})
    assert ctx.session.user.role == "secretary"
    assert not ctx.session.can("users.manage")


def test_attendance_requires_valid_hhmm_and_employee(env):
    _, svc = env
    employee_id = svc.teachers.create({
        "employee_no": "ENS002", "first_name": "Soa", "last_name": "Rabe",
        "gender": "F", "birth_date": "1985-01-01", "hire_date": "2020-09-01"})
    with pytest.raises(ValidationError, match="format attendu HH:MM"):
        svc.attendance.create({"employee_id": employee_id, "attendance_date": "2026-11-10",
                               "status": "present", "arrival_time": "7:30", "departure_time": "17:00"})
    with pytest.raises(ValidationError, match="Employé"):
        svc.attendance.create({"attendance_date": "2026-11-10", "status": "present",
                               "arrival_time": "08:00", "departure_time": "17:00"})


def test_statement_message_includes_school_year(env):
    _, svc = env
    class_id = svc.classes.create({"name": "CP", "school_year": "2026-2027"})
    svc.students.select_school_year("2026-2027")
    student_id = svc.students.create({**VALID, "class_id": class_id})
    with pytest.raises(ValidationError, match=r"classe CP 2026-2027"):
        svc.payments.statement(student_id)


def test_user_listing_never_exposes_hash(env):
    _, svc = env
    assert "password_hash" not in svc.users.page().rows[0].keys()


def test_removed_grade_tables_are_not_exposed(env):
    ctx, svc = env
    tables = {row["name"] for row in ctx.db.all(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert "subjects" not in tables
    assert "grades" not in tables
    assert not hasattr(svc, "subjects")
    assert not hasattr(svc, "grades")


def test_students_can_be_enrolled_in_preschool_ages(env):
    _, svc = env
    student_id = svc.students.create({**VALID, "birth_date": "2024-05-12"})
    assert svc.students.get(student_id)["birth_date"] == "2024-05-12"


def test_demo_seed_uses_school_levels_and_age_ranges(tmp_path, monkeypatch):
    from scripts.seed_demo import main as seed_demo

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "school.db")
    monkeypatch.setattr(config, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(config, "LOG_DIR", tmp_path / "logs")
    seed_demo(len(school.SCHOOL_LEVELS))

    db = Database(config.DB_PATH)
    try:
        classes = db.all("SELECT id, name FROM classes")
        assert {row["name"] for row in classes} == set(school.SCHOOL_LEVELS)
        students = db.all(
            "SELECT s.birth_date, c.name FROM students s "
            "JOIN student_enrollments e ON e.student_id=s.id "
            "JOIN classes c ON c.id=e.class_id")
        assert len(students) == len(school.SCHOOL_LEVELS)
        today = date.today()
        for student in students:
            level = student["name"]
            birth_date = date.fromisoformat(student["birth_date"])
            age = today.year - birth_date.year - (
                (today.month, today.day) < (birth_date.month, birth_date.day))
            minimum, maximum = school.LEVEL_AGE_RANGES[level]
            assert minimum <= age <= maximum
    finally:
        db.close()


def test_demo_seed_replaces_school_data_but_keeps_accounts(tmp_path, monkeypatch):
    from scripts.seed_demo import main as seed_demo

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "school.db")
    monkeypatch.setattr(config, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(config, "LOG_DIR", tmp_path / "logs")
    db = Database(config.DB_PATH)
    try:
        migrate(db)
        db.execute(
            "INSERT INTO users(username,password_hash,full_name,role) VALUES(?,?,?,?)",
            ("admin", "hash", "Admin", "admin"))
        db.execute(
            "INSERT INTO teachers(employee_no,first_name,last_name,hire_date) "
            "VALUES('OLD','Aina','Rabe','2020-09-01')")
        db.execute("INSERT INTO classes(name,school_year) VALUES('Ancienne classe','2025-2026')")
        db.execute(
            "INSERT INTO students(matricule,first_name,last_name,birth_date,class_id) "
            "VALUES('OLD1','Miora','Rabe','2010-01-01',1)")
        db.execute(
            "INSERT INTO student_enrollments(student_id,school_year,class_id) VALUES(1,'2025-2026',1)")
    finally:
        db.close()

    seed_demo(len(school.SCHOOL_LEVELS), replace_demo=True)

    db = Database(config.DB_PATH)
    try:
        assert db.one("SELECT COUNT(*) FROM users")[0] == 1
        assert db.one("SELECT COUNT(*) FROM students")[0] == len(school.SCHOOL_LEVELS)
        assert {r["name"] for r in db.all("SELECT name FROM classes")} == set(school.SCHOOL_LEVELS)
        assert db.one("SELECT COUNT(*) FROM student_enrollments")[0] == len(school.SCHOOL_LEVELS)
        assert db.one("SELECT COUNT(*) FROM employee_school_years")[0] == 40
    finally:
        db.close()


def test_fees_and_payments(env):
    ctx, svc = env
    year = "2026-2027"
    class_id = svc.classes.create({"name": "Classe A", "school_year": year})
    student_id = svc.students.create({**VALID, "class_id": class_id, "tuition_discount": 20})
    svc.fees.create({"class_id": class_id, "monthly_amount": 2500, "droit_amount": 1000,
                     "photocopy_amount": 200, "uniform_amount": 300, "activity_1_amount": 400})

    statement = svc.payments.statement(student_id)
    assert statement["rows"][0]["due"] == 1000
    assert statement["rows"][3]["label"] == "Septembre"
    assert statement["rows"][3]["due"] == 2000
    assert [row["label"] for row in statement["rows"]] == [
        "Droit", "Photocopie", "Tenue", "Septembre", "Octobre", "Novembre", "Décembre",
        "Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Calendrier", "Classe verte",
        "Enveloppe", "Fête de fin d'année", "Autre"]
    assert tuple(school.FEE_ITEM_LABELS[code] for code in school.ACTIVITY_FEE_CODES) == (
        "Calendrier", "Classe verte", "Enveloppe", "Fête de fin d'année", "Autre")
    assert len(statement["rows"]) == 18
    assert statement["total_due"] == 1000 + 200 + 300 + 400 + 10 * 2000

    payment_id, receipt = svc.payments.record(
        student_id, {"kind": "registration", "amount": 1000, "method": "cash"})
    assert receipt.startswith("R2026-")
    assert svc.payments.statement(student_id)["total_paid"] == 1000

    svc.payments.cancel(payment_id, "Erreur de saisie")
    assert svc.payments.receipt_data(payment_id)["cancelled"] == 1
    assert svc.payments.statement(student_id)["total_paid"] == 0
    with pytest.raises(sqlite3.IntegrityError, match="Paiement non modifiable"):
        ctx.db.execute("UPDATE payments SET amount = 500 WHERE id = ?", (payment_id,))

    svc.payments.record(student_id, {"fee_code": "photocopie", "amount": 200, "method": "cash"})
    assert svc.payments.statement(student_id)["rows"][1]["paid"] == 200


def test_payment_history_reports_gender_and_settlement_state(env):
    _, svc = env
    class_id = svc.classes.create({"name": "Classe Paiements", "school_year": "2026-2027"})
    student_id = svc.students.create({**VALID, "class_id": class_id, "gender": "F"})
    svc.fees.create({"class_id": class_id, "monthly_amount": 0, "photocopy_amount": 200})

    first_id, _ = svc.payments.record(
        student_id, {"fee_code": "photocopie", "amount": 100, "method": "cash"})
    first = svc.payments.page().rows[0]
    assert first["gender"] == "F"
    assert first["payment_status"] == "Partiel"

    second_id, _ = svc.payments.record(
        student_id, {"fee_code": "photocopie", "amount": 100, "method": "cash"})
    rows = {row["id"]: row for row in svc.payments.page().rows}
    assert rows[first_id]["payment_status"] == "Payé totalement"
    assert rows[second_id]["payment_status"] == "Payé totalement"

    svc.payments.cancel(second_id, "Erreur de saisie")
    rows = {row["id"]: row for row in svc.payments.page().rows}
    assert rows[second_id]["payment_status"] == "Annulé"
    assert rows[first_id]["payment_status"] == "Partiel"


def test_payment_history_is_grouped_by_class_and_school_year(env):
    _, svc = env
    classes = [
        ("Classe Z", "2025-2026"),
        ("Classe B", "2026-2027"),
        ("Classe A", "2026-2027"),
    ]
    for name, year in classes:
        class_id = svc.classes.create({"name": name, "school_year": year})
        svc.students.select_school_year(year)
        student_id = svc.students.create({**VALID, "first_name": name.replace(" ", ""), "class_id": class_id})
        svc.fees.create({"class_id": class_id, "monthly_amount": 0, "droit_amount": 200})
        svc.payments.record(student_id, {"fee_code": "droit", "amount": 100, "method": "cash"})

    history = svc.payments.page().rows
    assert [(row["class_name"], row["school_year"]) for row in history] == [
        ("Classe A", "2026-2027"), ("Classe B", "2026-2027"), ("Classe Z", "2025-2026")]


def test_arrears_respect_the_class_school_year(env):
    _, svc = env
    old_year = "2025-2026"
    future_year = "2027-2028"
    old_class = svc.classes.create({"name": "Classe ancienne", "school_year": old_year})
    future_class = svc.classes.create({"name": "Classe future", "school_year": future_year})
    svc.students.select_school_year(old_year)
    svc.students.create({**VALID, "class_id": old_class})
    svc.students.select_school_year(future_year)
    svc.students.create({**VALID, "first_name": "Aina", "class_id": future_class})
    svc.fees.create({"class_id": old_class, "monthly_amount": 1000})
    svc.fees.create({"class_id": future_class, "monthly_amount": 1000})

    arrears = svc.payments.arrears(class_id=old_class, today=date(2026, 9, 15))
    assert sum(row["balance"] for row in arrears) == 10000
    assert len(arrears) == 10
    assert svc.payments.arrears(class_id=future_class, today=date(2026, 9, 15)) == []


def test_arrears_filter_class_year_month_and_csv_export(env, tmp_path):
    _, svc = env
    class_id = svc.classes.create({"name": "Classe Impayés", "school_year": "2026-2027"})
    student_id = svc.students.create({
        **VALID, "class_id": class_id, "gender": "F", "matricule": "IMP001"})
    svc.fees.create({
        "class_id": class_id, "monthly_amount": 1000, "droit_amount": 500,
        "photocopy_amount": 250,
    })
    svc.payments.record(
        student_id, {"fee_code": "photocopie", "amount": 250, "method": "cash"})

    all_arrears = svc.payments.arrears(
        class_id=class_id, school_year="2026-2027", today=date(2026, 10, 15))
    assert {(row["fee_code"], row["month"]) for row in all_arrears} == {
        ("droit", None), ("september", 9), ("october", 10)}
    assert all(row["class_name"] == "Classe Impayés" for row in all_arrears)
    assert all(row["gender"] == "F" and row["matricule"] == "IMP001" for row in all_arrears)

    october = svc.payments.arrears(
        class_id=class_id, school_year="2026-2027", month=10, today=date(2026, 10, 15))
    assert [(row["fee_code"], row["balance"]) for row in october] == [("october", 1000)]
    assert svc.payments.arrears(
        class_id=class_id, school_year="2026-2027", month=11, today=date(2026, 10, 15)) == []

    path = tmp_path / "arrears.csv"
    count = svc.payments.export_arrears_csv(
        path, class_id=class_id, school_year="2026-2027", month=10,
        today=date(2026, 10, 15))
    exported = path.read_text(encoding="utf-8-sig")
    assert count == 1
    assert "Poste impayé" in exported and "Féminin" in exported
    assert "Écolage" in exported and "Octobre" in exported and "Droit" not in exported
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_arrears_page_is_filtered_and_matches_complete_report(env):
    _, svc = env
    class_id = svc.classes.create({"name": "Classe Page", "school_year": "2026-2027"})
    student_ids = [
        svc.students.create({
            **VALID, "first_name": ("Aina", "Bao", "Soa")[i], "class_id": class_id})
        for i in range(3)
    ]
    svc.fees.create({"class_id": class_id, "monthly_amount": 1000})
    for student_id in student_ids:
        svc.payments.record(
            student_id, {"fee_code": "october", "amount": 200, "method": "cash"})

    report = svc.payments.arrears(
        class_id=class_id, school_year="2026-2027", month=10, today=date(2026, 10, 15))
    first_page = svc.payments.arrears_page(
        class_id=class_id, school_year="2026-2027", month=10, today=date(2026, 10, 15),
        page=0, size=2)
    second_page = svc.payments.arrears_page(
        class_id=class_id, school_year="2026-2027", month=10, today=date(2026, 10, 15),
        page=1, size=2)

    assert first_page["total"] == len(report) == 3
    assert first_page["students"] == 3
    assert first_page["balance"] == sum(row["balance"] for row in report) == 2400
    assert first_page["rows"] + second_page["rows"] == report


def test_dashboard_and_billing_permissions():
    from tests.conftest import make_env

    _, admin = make_env("admin")
    _, secretary = make_env("secretary")
    _, teacher = make_env("teacher")
    assert "collected_year" in admin.dashboard.summary()
    assert "collected_year" in secretary.dashboard.summary()
    assert "collected_year" not in teacher.dashboard.summary()
    with pytest.raises(PermissionDenied):
        teacher.payments.statement(1)


def test_expense_service_records_and_validates(env):
    ctx, svc = env
    expense_id = svc.expenses.create({
        "category": "loyer", "label": "Loyer septembre",
        "amount": 500000, "expense_date": "2026-09-05"})
    row = svc.expenses.get(expense_id)
    assert (row["category"], row["amount"], row["expense_date"]) == ("loyer", 500000, "2026-09-05")
    assert row["created_by"] == ctx.session.user.id
    assert svc.expenses.page().total == 1

    for bad in ({"category": "inconnue", "amount": 1000, "expense_date": "2026-09-05"},
                {"category": "eau", "amount": 0, "expense_date": "2026-09-05"},
                {"category": "eau", "amount": 1000, "expense_date": "pas-une-date"}):
        with pytest.raises(ValidationError):
            svc.expenses.create(bad)


def test_expenses_are_reserved_to_finance_roles():
    from tests.conftest import make_env

    _, admin = make_env("admin")
    _, secretary = make_env("secretary")
    _, teacher = make_env("teacher")
    payload = {"category": "eau", "amount": 20000, "expense_date": "2026-09-10"}
    assert admin.expenses.create(payload) > 0
    assert secretary.expenses.create(payload) > 0
    with pytest.raises(PermissionDenied):
        teacher.expenses.create(payload)


def test_dashboard_finance_series_follows_profit_formula(env):
    ctx, svc = env
    year = "2026-2027"
    class_id = svc.classes.create({"name": "Classe Bénéfice", "school_year": year})
    student_id = svc.students.create({**VALID, "class_id": class_id})
    teacher_id = svc.teachers.create({
        "employee_no": "ENS900", "first_name": "Aina", "last_name": "Rakoto",
        "gender": "F", "birth_date": "1985-01-01", "hire_date": "2010-01-01",
        "position": "Maîtresse"})

    insert = lambda sql, params=(): ctx.db.execute(sql, params)
    for paid_at, amount, cancelled in (("2026-09-10", 1000000, 0), ("2026-09-25", 500000, 0),
                                       ("2026-09-15", 999999, 1), ("2026-10-05", 800000, 0)):
        insert("INSERT INTO payments (student_id, school_year, kind, month, fee_code, amount, "
               "method, paid_at, cancelled) VALUES (?, ?, 'registration', NULL, 'droit', ?, 'cash', ?, ?)",
               (student_id, year, amount, paid_at, cancelled))
    for payout_date, amount in (("2026-09-30", 400000), ("2026-10-15", 250000)):
        insert("INSERT INTO salary_disbursements (employee_id, title, payout_date, school_year, amount) "
               "VALUES (?, 'Salaire', ?, ?, ?)", (teacher_id, payout_date, year, amount))
    for category, expense_date, amount in (("loyer", "2026-09-01", 600000),
                                           ("electricite", "2026-09-20", 120000),
                                           ("eau", "2026-09-20", 30000),
                                           ("autre", "2026-09-28", 50000),
                                           ("loyer", "2026-10-01", 600000)):
        insert("INSERT INTO expenses (category, label, amount, expense_date) VALUES (?, '', ?, ?)",
               (category, amount, expense_date))

    series = svc.dashboard.finance_series(year, today=date(2026, 9, 20))
    assert series["school_year"] == year
    assert len(series["months"]) == len(school.SCHOOL_MONTHS) + 2   # + juillet et août
    by_ym = {month["ym"]: month for month in series["months"]}

    september = by_ym["2026-09"]
    assert (september["collected"], september["salaries"]) == (1500000, 400000)
    assert (september["loyer"], september["utilities"], september["other"]) == (600000, 150000, 50000)
    assert september["expenses"] == 800000
    assert september["spending"] == 1200000
    assert september["profit"] == 300000
    assert september["profit"] == september["collected"] - (
        september["salaries"] + september["loyer"] + september["utilities"] + september["other"])

    october = by_ym["2026-10"]
    assert october["profit"] == 800000 - (250000 + 600000)
    assert october["profit"] < 0

    totals = series["totals"]
    assert totals["collected"] == 2300000
    assert totals["spending"] == 2050000
    assert totals["profit"] == 250000
    assert series["default_index"] == 0


def test_finance_series_is_none_without_finance_access():
    from tests.conftest import make_env

    _, teacher = make_env("teacher")
    assert teacher.dashboard.finance_available() is False
    assert teacher.dashboard.finance_series("2026-2027") is None


def test_class_fee_migration_preserves_legacy_fees_and_payments():
    from app.database.migration2 import MIGRATION_2
    from app.database.migration3 import MIGRATION_3

    db = Database()
    try:
        db.conn.executescript(f"{MIGRATION_1}\n{MIGRATION_2}\nPRAGMA user_version=2;")
        db.execute("INSERT INTO classes (name, level, school_year) VALUES ('6e-A', '6e', '2026-2027')")
        db.execute("INSERT INTO tuition_fees (level, school_year, monthly_amount, registration_fee) "
                   "VALUES ('6e', '2026-2027', 2500, 1000)")
        db.execute("INSERT INTO students (matricule, first_name, last_name, birth_date, class_id, guardian_name) "
                   "VALUES ('E1', 'Aina', 'Rabe', '2010-01-01', 1, 'Ancien tuteur')")
        db.execute("INSERT INTO payments (student_id, school_year, kind, month, amount, method) "
                   "VALUES (1, '2026-2027', 'monthly', 10, 2500, 'cash')")

        migrate(db)

        fee = db.one("SELECT * FROM class_tuition_fees WHERE class_id = 1")
        payment = db.one("SELECT fee_code FROM payments WHERE student_id = 1")
        student = db.one("SELECT tutor_name FROM students WHERE id = 1")
        school_class = db.one("SELECT name, school_year FROM classes WHERE id = 1")
        assert (fee["monthly_amount"], fee["droit_amount"]) == (2500, 1000)
        assert payment["fee_code"] == "october"
        assert student["tutor_name"] == "Ancien tuteur"
        assert (school_class["name"], school_class["school_year"]) == ("6e-A", "2026-2027")
        assert db.one("SELECT name FROM sqlite_master WHERE type='table' AND name='tuition_fees'") is None
        assert "level" not in {row["name"] for row in db.all("PRAGMA table_info(classes)")}
        with pytest.raises(sqlite3.IntegrityError, match="Paiement non modifiable"):
            db.execute("UPDATE payments SET fee_code = 'september' WHERE student_id = 1")
    finally:
        db.close()


def test_csv_import_export_and_formula_injection(env, tmp_path):
    ctx, svc = env
    f = tmp_path / "in.csv"
    f.write_text("matricule,first_name,last_name,birth_date,tutor_phone,father_phone,mother_phone,"
                 "tutor_profession,father_profession,mother_profession\n"
                 "M1,Anna,Rabe,2010-01-01,0341234567,0321234567,0331234567,Enseignant,"
                 "Agriculteur,Commerçante\n"
                 "M1,Anna,Rabe,2010-01-01,0341234567,0321234567,0331234567,Enseignant,"
                 "Agriculteur,Commerçante\n,Bob,<b>,2010-01-01,,,,,,\n"
                 ",=cmd,Rabe,2010-01-01,,,,,,\n", encoding="utf-8")
    rep = svc.students.import_csv(f)
    assert rep.inserted == 1 and rep.duplicates == 1 and len(rep.errors) == 2
    student = svc.students.get(1)
    assert tuple(student[key] for key in ("tutor_phone", "father_phone", "mother_phone")) == (
        "0341234567", "0321234567", "0331234567")
    assert tuple(student[key] for key in (
        "tutor_profession", "father_profession", "mother_profession")) == (
            "Enseignant", "Agriculteur", "Commerçante")
    svc.students.update(1, {"first_name": "Anna", "last_name": "Rabe", "birth_date": "2010-01-01",
                            "address": "=HYPERLINK(\"http://x\")",
                            "tutor_phone": "0341234567", "father_phone": "0321234567",
                            "mother_phone": "0331234567", "tutor_profession": "Enseignant",
                            "father_profession": "Agriculteur", "mother_profession": "Commerçante"})
    out = tmp_path / "out.csv"
    out.write_text("ancienne exportation", encoding="utf-8")
    out.chmod(0o644)
    assert svc.students.export_csv(out) == 1
    assert stat.S_IMODE(out.stat().st_mode) == 0o600
    assert "'=HYPERLINK" in out.read_text(encoding="utf-8-sig")
    exported = out.read_text(encoding="utf-8-sig")
    assert all(phone in exported for phone in ("0341234567", "0321234567", "0331234567"))
    assert all(profession in exported for profession in (
        "Enseignant", "Agriculteur", "Commerçante"))


def test_backups_are_private_and_use_unique_names(env, tmp_path, monkeypatch):
    _, svc = env
    monkeypatch.setattr(config, "BACKUP_DIR", tmp_path)

    first = svc.backup.backup()
    second = svc.backup.backup()

    assert first != second
    assert stat.S_IMODE(os.stat(first).st_mode) == 0o600


def test_backup_failure_does_not_leave_a_partial_pair(env, tmp_path, monkeypatch):
    _, svc = env
    monkeypatch.setattr(config, "BACKUP_DIR", tmp_path)
    original_copy = svc.backup._copy
    calls = 0

    def fail_on_accounts(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("accounts backup failed")
        original_copy(source, destination)

    monkeypatch.setattr(svc.backup, "_copy", fail_on_accounts)
    with pytest.raises(OSError, match="accounts backup failed"):
        svc.backup.backup_before_migration()

    assert list(tmp_path.iterdir()) == []


def test_recreated_username_does_not_break_school_mirror_or_history(env):
    from app.database.accounts import mirror_users
    ctx, svc = env
    jean = svc.users.create({"username": "jean", "full_name": "Jean", "role": "secretary",
                             "password": "Str0ng!Passw0rd2"})
    mirror_users(ctx.accounts, ctx.db)
    svc.users.delete(jean)
    marie = svc.users.create({"username": "marie", "full_name": "Marie", "role": "secretary",
                              "password": "Str0ng!Passw0rd2"})
    assert marie != jean                                   # identifiant jamais réattribué
    again = svc.users.create({"username": "jean", "full_name": "Jean (retour)", "role": "secretary",
                              "password": "Str0ng!Passw0rd2"})
    mirror_users(ctx.accounts, ctx.db)                     # ne doit pas lever d'IntegrityError
    names = {r["id"]: r["full_name"] for r in ctx.db.all("SELECT id, full_name FROM users")}
    assert names[jean] == "Jean" and names[again] == "Jean (retour)"   # l'historique n'est pas réécrit


def test_exported_students_can_be_reimported_with_their_class(env, tmp_path):
    ctx, svc = env
    year = school.current_school_year()
    class_id = svc.classes.create({"name": "CP", "school_year": year})
    svc.students.create({**VALID, "birth_date": "2019-03-01", "class_id": class_id})
    out = tmp_path / "e.csv"
    svc.students.export_csv(out)
    ctx2, svc2 = make_env("admin")
    class2 = svc2.classes.create({"name": "CP", "school_year": year})
    assert svc2.students.import_csv(out).inserted == 1
    assert svc2.students.page().rows[0]["class_id"] == class2


def test_finance_series_counts_july_and_august(env):
    ctx, svc = env
    year = "2026-2027"
    class_id = svc.classes.create({"name": "Eté", "school_year": year})
    student_id = svc.students.create({**VALID, "class_id": class_id})
    ctx.db.execute("INSERT INTO payments (student_id, school_year, kind, month, fee_code, amount, "
                   "method, paid_at) VALUES (?, ?, 'registration', NULL, 'droit', 5000, 'cash', '2027-07-20')",
                   (student_id, year))
    ctx.db.execute("INSERT INTO expenses (category, label, amount, expense_date) "
                   "VALUES ('loyer', '', 300000, '2027-07-05')")
    series = svc.dashboard.finance_series(year, today=date(2026, 9, 20))
    assert series["totals"]["collected"] == 5000 and series["totals"]["loyer"] == 300000
    assert [m["ym"] for m in series["months"]][-2:] == ["2027-07", "2027-08"]
