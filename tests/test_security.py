import pytest

from app.core import security
from app.core.exceptions import AuthenticationError, PermissionDenied, ValidationError
from app.core.session import Session


def test_hash_and_verify():
    h = security.hash_password("Abcdefg#123")
    assert h != "Abcdefg#123" and security.verify_password("Abcdefg#123", h)
    assert not security.verify_password("autre", h)
    assert not security.verify_password("x", "format-invalide")


def test_password_policy():
    with pytest.raises(ValidationError):
        security.check_password_policy("faible")
    security.check_password_policy("Abcdefg#123")


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
