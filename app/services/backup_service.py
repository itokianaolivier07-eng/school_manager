"""Sauvegarde à chaud (API backup de SQLite) avec contrôle d'intégrité et rotation."""
import os
import sqlite3
from datetime import datetime

from app import config
from app.core.exceptions import AppError
from app.repositories.repos import AuditRepository


class BackupService:
    def __init__(self, ctx):
        self.ctx = ctx
        self.audit = AuditRepository(ctx.db)

    def backup(self) -> str:
        user = self.ctx.session.require("backup.run")
        config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        dest = config.BACKUP_DIR / f"school_{datetime.now():%Y%m%d_%H%M%S}.db"
        os.close(os.open(dest, os.O_CREAT | os.O_WRONLY, 0o600))
        target = sqlite3.connect(dest)
        try:
            self.ctx.db.conn.backup(target)
            if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise AppError("La sauvegarde créée est corrompue.")
        finally:
            target.close()
        old = sorted(config.BACKUP_DIR.glob("school_*.db"))[:-config.BACKUP_KEEP]
        for f in old:
            f.unlink(missing_ok=True)
        self.audit.log(user, "backup", "database", None, dest.name)
        return str(dest)
