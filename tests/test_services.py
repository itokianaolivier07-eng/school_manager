import os
import sqlite3
import stat
import time
from datetime import date

import pytest

from app import config
from app.core.exceptions import AuthenticationError, DuplicateError, PermissionDenied, ValidationError
from app.database.connection import Database
from app.database.schema import MIGRATION_1, migrate
from app.repositories.repos import AuditRepository
from tests.conftest import make_env

VALID = {"first_name": "Miora", "last_name": "Rakoto", "birth_date": "2010-05-12"}


def test_create_student_autogenerates_matricule(env):
    ctx, svc = env
    sid = svc.students.create(VALID)
    row = svc.students.get(sid)
    assert row["matricule"].startswith("E") and row["status"] == "active"


def test_student_schema_and_legacy_contact_privacy(env):
    ctx, svc = env
    assert ctx.db.one("PRAGMA user_version")[0] == 6
    class_columns = {row["name"] for row in ctx.db.all("PRAGMA table_info(classes)")}
    assert "level" not in class_columns
    assert ctx.db.one("SELECT name FROM sqlite_master WHERE type='table' AND name='tuition_fees'") is None
    columns = {row["name"] for row in ctx.db.all("PRAGMA table_info(students)")}
    assert {"guardian_name", "tutor_name", "father_name", "mother_name",
            "tuition_discount", "email", "phone"} <= columns

    student_id = svc.students.create({**VALID, "email": "ancien@example.test"})
    assert "email" not in svc.students.get(student_id)
    assert "phone" not in svc.students.get(student_id)


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
                     "tuition_discount FROM students WHERE matricule='E1'")
        assert tuple(row) == ("ancien@example.test", "12345678", None, None, None, None, 0)
        teacher = db.one("SELECT position FROM teachers WHERE employee_no='ENS001'")
        assert teacher["position"] == "Enseignante"
        assert db.one("PRAGMA user_version")[0] == 6
        class_columns = {row["name"] for row in db.all("PRAGMA table_info(classes)")}
        assert "level" not in class_columns
    finally:
        db.close()


def test_validation_rejects_bad_input(env):
    _, svc = env
    for bad in ({**VALID, "first_name": "<script>"}, {**VALID, "birth_date": "2999-01-01"},
                {**VALID, "birth_date": "2020-01-01"}, {**VALID, "gender": "X"}):
        with pytest.raises(ValidationError):
            svc.students.create(bad)


def test_class_without_level_and_optional_parent_names(env):
    _, svc = env
    class_id = svc.classes.create({"name": "Classe A", "school_year": "2026-2027"})
    class_row = svc.classes.get(class_id)
    assert "level" not in class_row
    student_id = svc.students.create({**VALID, "class_id": class_id})
    student = svc.students.get(student_id)
    assert (student["tutor_name"], student["father_name"], student["mother_name"]) == (None, None, None)

    svc.students.update(student_id, {**VALID, "matricule": student["matricule"], "class_id": class_id,
                                     "tutor_name": "Tuteur", "father_name": "Père", "mother_name": "Mère"})
    student = svc.students.get(student_id)
    assert (student["tutor_name"], student["father_name"], student["mother_name"]) == (
        "Tuteur", "Père", "Mère")


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
    assert svc.students.page().total == 1


def test_30000_students_pagination_and_search(env):
    ctx, svc = env
    rows = [{"matricule": f"E{i:07d}", "first_name": "Jean", "last_name": f"Nom{i % 500:03d}",
             "birth_date": "2010-01-01", "status": "active"} for i in range(30000)]
    with ctx.db.transaction():
        svc.students.repo.bulk_insert(rows)
    t = time.perf_counter()
    p = svc.students.page(page=150, sort="last_name")
    s = svc.students.page(search="Nom042")
    elapsed = time.perf_counter() - t
    assert p.total == 30000 and len(p.rows) == config.PAGE_SIZE and p.pages == 300
    assert s.total == 60
    assert elapsed < 1.0, f"trop lent : {elapsed:.2f}s"


def test_audit_log_is_append_only(env):
    ctx, svc = env
    svc.students.create(VALID)
    assert AuditRepository(ctx.db).count() >= 1
    with pytest.raises(Exception):
        ctx.db.execute("DELETE FROM audit_log")
    with pytest.raises(Exception):
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


def test_user_listing_never_exposes_hash(env):
    _, svc = env
    assert "password_hash" not in svc.users.page().rows[0].keys()


def test_grades_and_ranking(env):
    ctx, svc = env
    cid = svc.classes.create({"name": "6e-A", "school_year": "2026-2027"})
    sub = svc.subjects.create({"code": "MATH", "name": "Maths", "coefficient": 4})
    ids = [svc.students.create({**VALID, "first_name": n, "class_id": cid}) for n in ("Aina", "Bao")]
    svc.grades.save_sheet(cid, sub, 1, [(ids[0], "12,5", None), (ids[1], 17, "Bien")])
    rank = svc.grades.ranking(cid, 1)
    assert [r["first_name"] for r in rank] == ["Bao", "Aina"] and rank[0]["rank"] == 1
    with pytest.raises(ValidationError):
        svc.grades.save_sheet(cid, sub, 1, [(ids[0], 25, None)])


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
        "Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Activité 1", "Activité 2",
        "Activité 3", "Activité 4", "Activité 5"]
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


def test_arrears_respect_the_class_school_year(env):
    _, svc = env
    old_year = "2025-2026"
    future_year = "2027-2028"
    old_class = svc.classes.create({"name": "Classe ancienne", "school_year": old_year})
    future_class = svc.classes.create({"name": "Classe future", "school_year": future_year})
    svc.students.create({**VALID, "class_id": old_class})
    svc.students.create({**VALID, "first_name": "Aina", "class_id": future_class})
    svc.fees.create({"class_id": old_class, "monthly_amount": 1000})
    svc.fees.create({"class_id": future_class, "monthly_amount": 1000})

    arrears = svc.payments.arrears(old_class, date(2026, 9, 15))
    assert arrears[0]["due"] == 10000
    assert svc.payments.arrears(future_class, date(2026, 9, 15)) == []


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
    f.write_text("matricule,first_name,last_name,birth_date\n"
                 "M1,Anna,Rabe,2010-01-01\nM1,Anna,Rabe,2010-01-01\n,Bob,<b>,2010-01-01\n"
                 ",=cmd,Rabe,2010-01-01\n", encoding="utf-8")
    rep = svc.students.import_csv(f)
    assert rep.inserted == 1 and rep.duplicates == 1 and len(rep.errors) == 2
    svc.students.update(1, {"first_name": "Anna", "last_name": "Rabe", "birth_date": "2010-01-01",
                            "address": "=HYPERLINK(\"http://x\")"})
    out = tmp_path / "out.csv"
    out.write_text("ancienne exportation", encoding="utf-8")
    out.chmod(0o644)
    assert svc.students.export_csv(out) == 1
    assert stat.S_IMODE(out.stat().st_mode) == 0o600
    assert "'=HYPERLINK" in out.read_text(encoding="utf-8-sig")


def test_backups_are_private_and_use_unique_names(env, tmp_path, monkeypatch):
    _, svc = env
    monkeypatch.setattr(config, "BACKUP_DIR", tmp_path)

    first = svc.backup.backup()
    second = svc.backup.backup()

    assert first != second
    assert stat.S_IMODE(os.stat(first).st_mode) == 0o600
