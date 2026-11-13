import time

import pytest

from app import config
from app.core.exceptions import AuthenticationError, DuplicateError, ValidationError
from app.repositories.repos import AuditRepository
from tests.conftest import make_env

VALID = {"first_name": "Miora", "last_name": "Rakoto", "birth_date": "2010-05-12"}


def test_create_student_autogenerates_matricule(env):
    ctx, svc = env
    sid = svc.students.create(VALID)
    row = svc.students.get(sid)
    assert row["matricule"].startswith("E") and row["status"] == "active"


def test_validation_rejects_bad_input(env):
    _, svc = env
    for bad in ({**VALID, "first_name": "<script>"}, {**VALID, "birth_date": "2999-01-01"},
                {**VALID, "email": "pas-un-email"}, {**VALID, "gender": "X"}):
        with pytest.raises(ValidationError):
            svc.students.create(bad)


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
    assert svc.students.export_csv(out) == 1
    assert "'=HYPERLINK" in out.read_text(encoding="utf-8-sig")
