"""Sauvegarde à chaud (API backup de SQLite) avec contrôle d'intégrité et rotation.

Sauvegarde la base de l'école active ET la base des comptes (accounts_*.db)."""
import os
import sqlite3
import time
from datetime import datetime

from app import config
from app.core.exceptions import AppError


class BackupService:
    AUTO_MIN_INTERVAL_HOURS = 20

    def __init__(self, ctx):
        self.ctx = ctx

    @staticmethod
    def _copy(source_conn, dest) -> None:
        os.close(os.open(dest, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
        try:
            target = sqlite3.connect(dest)
            try:
                source_conn.backup(target)
                if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise AppError("La sauvegarde créée est corrompue.")
            finally:
                target.close()
        except Exception:
            dest.unlink(missing_ok=True)
            raise

    @staticmethod
    def _rotate(pattern) -> None:
        for old in sorted(config.BACKUP_DIR.glob(pattern))[:-config.BACKUP_KEEP]:
            old.unlink(missing_ok=True)

    def _run(self) -> str:
        config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = f"{datetime.now():%Y%m%d_%H%M%S_%f}"
        dest = config.BACKUP_DIR / f"school_{stamp}.db"
        self._copy(self.ctx.db.conn, dest)
        if self.ctx.accounts is not None:
            self._copy(self.ctx.accounts.conn, config.BACKUP_DIR / f"accounts_{stamp}.db")
        self._rotate("school_*.db")
        self._rotate("accounts_*.db")
        return str(dest)

    def backup(self) -> str:
        self.ctx.session.require("backup.run")
        return self._run()

    def auto_backup(self):
        """Sauvegarde silencieuse à l'ouverture d'une école (au plus une toutes les 20 h)."""
        existing = list(config.BACKUP_DIR.glob("school_*.db")) if config.BACKUP_DIR.exists() else []
        if existing and time.time() - max(f.stat().st_mtime for f in existing) \
                < self.AUTO_MIN_INTERVAL_HOURS * 3600:
            return None
        return self._run()
