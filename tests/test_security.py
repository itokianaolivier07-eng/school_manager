from datetime import date

import pytest

from app.core import security
from app.core import school
from app.core.exceptions import AuthenticationError, PermissionDenied, ValidationError
from app.core.session import Session
from app.core.validators import integer, school_year


def test_hash_and_verify():
    h = security.hash_password("Abcdefg#123")
    assert h != "Abcdefg#123" and security.verify_password("Abcdefg#123", h)
    assert not security.verify_password("autre", h)
    assert not security.verify_password("x", "format-invalide")


def test_password_policy():
    with pytest.raises(ValidationError):
        security.check_password_policy("faible")
    security.check_password_policy("Abcdefg#123")


@pytest.mark.parametrize("value", [1.5, True, "1.5"])
def test_integer_rejects_fractional_and_boolean_values(value):
    with pytest.raises(ValidationError):
        integer({"value": value}, "value", "Montant", required=True)


def test_school_year_validation_and_boundaries():
    assert school_year({"year": "2026-2027"}, "year") == "2026-2027"
    with pytest.raises(ValidationError):
        school_year({"year": "2026-2028"}, "year")
    assert school.current_school_year(date(2026, 8, 31)) == "2025-2026"
    assert school.current_school_year(date(2026, 9, 1)) == "2026-2027"
    assert school.months_elapsed(date(2026, 9, 30)) == 1


def test_session_expiry_and_permissions(env):
    ctx, _ = env
    s = Session(timeout_seconds=-1)
    s.login(ctx.session.user)
    with pytest.raises(AuthenticationError):
        s.require("students.read")


def test_teacher_cannot_write_students(teacher_env):
    _, svc = teacher_env
    with pytest.raises(PermissionDenied):
        svc.students.create({"first_name": "A", "last_name": "B", "birth_date": "2010-01-01"})
    with pytest.raises(PermissionDenied):
        svc.users.page()
