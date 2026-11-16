import pytest

from app.repositories.base import BaseRepository

PAYLOADS = ["'; DROP TABLE students; --", "' OR '1'='1", "%' UNION SELECT password_hash FROM users --",
            "1; DELETE FROM classes", '" OR ""="', "\\", "%", "_"]
TABLES = ("students", "classes", "teachers", "users")


def _tables(db):
    return {r[0] for r in db.all("SELECT name FROM sqlite_master WHERE type='table'")}


@pytest.mark.parametrize("payload", PAYLOADS)
def test_search_and_sort_payloads_are_harmless(env, payload):
    ctx, svc = env
    before = _tables(ctx.db)
    for service in (svc.students, svc.classes, svc.teachers):
        page = service.page(search=payload, sort=payload, desc=True)
        for row in page.rows:
            assert "password_hash" not in dict(row)
    assert _tables(ctx.db) == before
    for table in TABLES:
        ctx.db.one(f"SELECT COUNT(*) FROM {table}")


def test_get_by_id_payload_does_not_match_everything(env):
    ctx, svc = env
    assert svc.students.repo.get("1 OR 1=1") is None


def test_stacked_statements_are_refused(env):
    ctx, _ = env
    with pytest.raises(Exception):
        ctx.db.execute("SELECT 1; DROP TABLE students")
    assert "students" in _tables(ctx.db)


def test_invalid_identifiers_are_rejected(env):
    ctx, _ = env

    class BadTable(BaseRepository):
        table = "students; DROP TABLE users"

    class BadColumn(BaseRepository):
        table = "students"
        columns = ("name) VALUES (1); --",)

    with pytest.raises(ValueError):
        BadTable(ctx.db)
    with pytest.raises(ValueError):
        BadColumn(ctx.db)
