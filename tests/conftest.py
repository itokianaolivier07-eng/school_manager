import pytest

from app import config
from app.core.context import AppContext
from app.core.security import hash_password
from app.core.session import CurrentUser, Session
from app.database.accounts import migrate_accounts, mirror_users
from app.database.connection import Database
from app.database.schema import migrate
from app.repositories.repos import UserRepository
from app.services import Services


def make_env(role="admin"):
    db = Database(":memory:")
    migrate(db)
    accounts = Database(":memory:")
    migrate_accounts(accounts)
    uid = UserRepository(accounts).insert({"username": role, "full_name": role.title(), "role": role,
                                           "password_hash": hash_password("Str0ng!Passw0rd")})
    mirror_users(accounts, db)
    session = Session(config.SESSION_TIMEOUT_SECONDS)
    session.login(CurrentUser(uid, role, role.title(), role))
    ctx = AppContext(db, session, accounts)
    return ctx, Services(ctx)


@pytest.fixture(scope="module", autouse=True)
def _isolated_data_dir(tmp_path_factory):
    """Isole les dossiers de données (thème, sauvegardes, journaux) du vrai $HOME."""
    root = tmp_path_factory.mktemp("school_data")
    originals = {name: getattr(config, name) for name in ("ROOT_DIR", "DATA_DIR", "DB_PATH", "BACKUP_DIR", "LOG_DIR")}
    config.ROOT_DIR = root
    config.DATA_DIR = root
    config.DB_PATH = root / "school.db"
    config.BACKUP_DIR = root / "backups"
    config.LOG_DIR = root / "logs"
    yield root
    for name, value in originals.items():
        setattr(config, name, value)


@pytest.fixture
def env():
    return make_env("admin")


@pytest.fixture
def teacher_env():
    return make_env("teacher")
