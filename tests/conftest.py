import pytest

from app import config
from app.core.context import AppContext
from app.core.security import hash_password
from app.core.session import CurrentUser, Session
from app.database.connection import Database
from app.database.schema import migrate
from app.repositories.repos import UserRepository
from app.services import Services


def make_env(role="admin"):
    db = Database(":memory:")
    migrate(db)
    uid = UserRepository(db).insert({"username": role, "full_name": role.title(), "role": role,
                                     "password_hash": hash_password("Str0ng!Passw0rd")})
    session = Session(config.SESSION_TIMEOUT_SECONDS)
    session.login(CurrentUser(uid, role, role.title(), role))
    ctx = AppContext(db, session)
    return ctx, Services(ctx)


@pytest.fixture
def env():
    return make_env("admin")


@pytest.fixture
def teacher_env():
    return make_env("teacher")
