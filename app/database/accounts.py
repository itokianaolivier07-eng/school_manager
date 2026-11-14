"""Comptes utilisateurs partagés : une seule authentification pour les trois écoles."""
VERSION = 1

SCHEMA = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(length(username) BETWEEN 3 AND 50),
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin','secretary','teacher')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0,1)),
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until REAL,
    must_change_password INTEGER NOT NULL DEFAULT 0 CHECK(must_change_password IN (0,1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_COLUMNS = ("id", "username", "password_hash", "full_name", "role", "is_active",
            "failed_attempts", "locked_until", "must_change_password", "created_at")


def migrate_accounts(db) -> None:
    if db.one("PRAGMA user_version")[0] >= VERSION:
        return
    db.conn.executescript(f"BEGIN;\n{SCHEMA}\nPRAGMA user_version={VERSION};\nCOMMIT;")


def mirror_users(accounts_db, school_db) -> None:
    """Recopie les comptes dans la base de l'école, pour la traçabilité des opérations
    (paiements encaissés par, écritures créées par) sans jamais supprimer un ancien compte."""
    columns = ", ".join(_COLUMNS)
    updates = ", ".join(f"{name}=excluded.{name}" for name in _COLUMNS if name != "id")
    rows = [tuple(row[name] for name in _COLUMNS)
            for row in accounts_db.all(f"SELECT {columns} FROM users")]
    with school_db.transaction():
        school_db.executemany(
            f"INSERT INTO users ({columns}) VALUES ({','.join('?' * len(_COLUMNS))}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}", rows)
