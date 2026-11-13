"""Connexion SQLite sécurisée + gestion de transactions."""
import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

log = logging.getLogger(__name__)


class Database:
    def __init__(self, path=":memory:"):
        self.path = str(path)
        in_memory = self.path == ":memory:"
        if not in_memory:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            if not os.path.exists(self.path):  # fichier créé en 0600
                os.close(os.open(self.path, os.O_CREAT | os.O_WRONLY, 0o600))
        self.conn = sqlite3.connect(self.path, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self._depth = 0
        c = self.conn
        c.execute("PRAGMA foreign_keys=ON")      # intégrité référentielle
        c.execute("PRAGMA trusted_schema=OFF")   # durcissement
        c.execute("PRAGMA secure_delete=ON")     # efface réellement les données supprimées
        c.execute("PRAGMA busy_timeout=5000")
        c.execute("PRAGMA temp_store=MEMORY")
        c.execute("PRAGMA cache_size=-65536")    # ~64 Mo de cache
        if not in_memory:
            c.execute("PRAGMA journal_mode=WAL")  # lectures/écritures concurrentes, plus rapide
            c.execute("PRAGMA synchronous=NORMAL")

    # --- requêtes (toujours paramétrées : jamais de concaténation de valeurs) ---
    def all(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()

    def one(self, sql, params=()):
        return self.conn.execute(sql, params).fetchone()

    def execute(self, sql, params=()):
        return self.conn.execute(sql, params)

    def executemany(self, sql, rows):
        return self.conn.executemany(sql, rows)

    @contextmanager
    def transaction(self):
        """Transaction atomique ; les appels imbriqués rejoignent la transaction externe."""
        if self._depth:
            self._depth += 1
            try:
                yield self.conn
            finally:
                self._depth -= 1
            return
        self.conn.execute("BEGIN IMMEDIATE")
        self._depth = 1
        try:
            yield self.conn
            self.conn.execute("COMMIT")
        except BaseException:
            self.conn.execute("ROLLBACK")
            raise
        finally:
            self._depth = 0

    def integrity_check(self) -> bool:
        return self.one("PRAGMA integrity_check")[0] == "ok"

    def close(self):
        self.conn.close()
