import sqlite3

import pytest

from app import config
from app.core.exceptions import AppError
from app.database.accounts import migrate_accounts
from app.database.connection import Database
from app.database.schema import MIGRATIONS, migrate


def test_newer_database_is_refused():
    db = Database(":memory:")
    db.execute(f"PRAGMA user_version={MIGRATIONS[-1][0] + 1}")
    with pytest.raises(AppError):
        migrate(db)
    accounts = Database(":memory:")
    accounts.execute("PRAGMA user_version=99")
    with pytest.raises(AppError):
        migrate_accounts(accounts)


def test_backup_is_copied_externally(env, tmp_path, monkeypatch):
    _, svc = env
    monkeypatch.setattr(config, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setenv("SCHOOL_BACKUP_DIR", str(tmp_path / "usb"))
    svc.backup.backup()
    copies = list((tmp_path / "usb" / config.DATA_DIR.name).glob("*.db"))
    assert len(copies) == 2 and svc.backup.external_error is None


def test_external_failure_keeps_local_backup(env, tmp_path, monkeypatch):
    _, svc = env
    monkeypatch.setattr(config, "BACKUP_DIR", tmp_path / "backups")
    blocker = tmp_path / "file"
    blocker.write_text("x")
    monkeypatch.setenv("SCHOOL_BACKUP_DIR", str(blocker))
    path = svc.backup.backup()
    assert svc.backup.external_error and (tmp_path / "backups").exists() and path


def test_restore_roundtrip_and_rejections(env, tmp_path, monkeypatch):
    ctx, svc = env
    monkeypatch.setattr(config, "BACKUP_DIR", tmp_path / "backups")
    saved = svc.backup.backup()
    ctx.db.execute("CREATE TABLE temoin(x)")
    svc.backup.restore(saved)
    assert ctx.db.integrity_check()
    assert ctx.db.one("SELECT name FROM sqlite_master WHERE name='temoin'") is None
    with pytest.raises(AppError):
        svc.backup.restore(saved.replace("school_", "accounts_"))
    junk = tmp_path / "junk.db"
    junk.write_bytes(b"not a database" * 50)
    with pytest.raises(AppError):
        svc.backup.restore(junk)
    with pytest.raises(AppError):
        svc.backup.restore(tmp_path / "absent.db")


def test_restore_requires_permission(teacher_env, tmp_path):
    _, svc = teacher_env
    with pytest.raises(Exception):
        svc.backup.restore(tmp_path / "x.db")
