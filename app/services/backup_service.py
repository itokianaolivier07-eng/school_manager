"""Sauvegarde à chaud (API backup de SQLite) avec contrôle d'intégrité et rotation.

Sauvegarde la base de l'école active ET la base des comptes (accounts_*.db)."""
import os
import logging
import shutil
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from app import config
from app.core.exceptions import AppError, NotFoundError
from app.database.accounts import mirror_users
from app.database.schema import MIGRATIONS, migrate
from app.services.audit import log_event

log = logging.getLogger(__name__)


class BackupService:
    AUTO_MIN_INTERVAL_HOURS = 20

    def __init__(self, ctx):
        self.ctx = ctx
        self.external_error = None

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
        destinations = [dest]
        if self.ctx.accounts is not None:
            destinations.append(config.BACKUP_DIR / f"accounts_{stamp}.db")
        try:
            self._copy(self.ctx.db.conn, dest)
            if self.ctx.accounts is not None:
                self._copy(self.ctx.accounts.conn, destinations[1])
        except BaseException:
            for path in destinations:
                try:
                    path.unlink(missing_ok=True)
                except OSError:
                    log.warning("Impossible de nettoyer une sauvegarde incomplète : %s",
                                path, exc_info=True)
            raise
        self._rotate("school_*.db")
        self._rotate("accounts_*.db")
        self._mirror_external(destinations)
        return str(dest)

    def _mirror_external(self, files) -> None:
        """Copie la sauvegarde hors du disque de travail ; un échec n'annule jamais la sauvegarde locale."""
        self.external_error = None
        target = config.external_backup_dir()
        if target is None:
            return
        try:
            target = target / config.DATA_DIR.name
            target.mkdir(parents=True, exist_ok=True)
            for source in files:
                shutil.copy2(source, target / source.name)
            for pattern in ("school_*.db", "accounts_*.db"):
                for old in sorted(target.glob(pattern))[:-config.BACKUP_KEEP]:
                    old.unlink(missing_ok=True)
        except OSError as exc:
            self.external_error = str(exc)
            log.warning("Copie externe de la sauvegarde impossible : %s", target, exc_info=True)

    @staticmethod
    def _open_readonly(path):
        return sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=ro", uri=True)

    def validate_backup_file(self, path) -> None:
        if not Path(path).is_file():
            raise NotFoundError("Fichier de sauvegarde introuvable.")
        try:
            conn = self._open_readonly(path)
            try:
                if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise AppError("Cette sauvegarde est corrompue.")
                version = conn.execute("PRAGMA user_version").fetchone()[0]
                tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            finally:
                conn.close()
        except sqlite3.DatabaseError as exc:
            raise AppError("Fichier de sauvegarde invalide.") from exc
        if version < 1 or "students" not in tables:
            raise AppError("Ce fichier n'est pas une sauvegarde de l'école (school_*.db).")
        if version > MIGRATIONS[-1][0]:
            raise AppError("Cette sauvegarde vient d'une version plus récente du logiciel.")

    def restore(self, path) -> str:
        """Remplace les données de l'école active par une sauvegarde ; les comptes sont conservés.
        Une copie de sécurité de l'état actuel est faite avant. Retourne le chemin de cette copie."""
        self.ctx.session.require("backup.run")
        self.validate_backup_file(path)
        safety = self._run()
        source = self._open_readonly(path)
        try:
            source.backup(self.ctx.db.conn)
        finally:
            source.close()
        db = self.ctx.db
        db.execute("PRAGMA foreign_keys=ON")
        if db.path != ":memory:":
            db.execute("PRAGMA journal_mode=WAL")
        migrate(db)
        if self.ctx.accounts is not None:
            mirror_users(self.ctx.accounts, db)
        if not db.integrity_check():
            raise AppError("La base restaurée est corrompue ; utilisez la copie de sécurité : " + safety)
        log_event(self.ctx, "restore", "backup", None, {"file": Path(path).name})
        return safety

    def backup_before_migration(self) -> str:
        """Conserve une copie cohérente des bases avant une mise à niveau du schéma."""
        return self._run()

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
