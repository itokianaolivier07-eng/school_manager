"""Comptes utilisateurs partagés : une seule authentification pour les trois écoles."""
from app.core.exceptions import AppError

VERSION = 2

_TABLE = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
SCHEMA = _TABLE   # nouvelle installation
_COLUMNS = ("id", "username", "password_hash", "full_name", "role", "is_active",
            "failed_attempts", "locked_until", "must_change_password", "created_at")
# v1 -> v2 : AUTOINCREMENT, pour qu'un identifiant supprimé ne soit jamais réattribué.
UPGRADE_2 = ("ALTER TABLE users RENAME TO users_v1;\n" + _TABLE +
             f"INSERT INTO users ({', '.join(_COLUMNS)}) SELECT {', '.join(_COLUMNS)} FROM users_v1;\n"
             "DROP TABLE users_v1;\n")


def migrate_accounts(db) -> None:
    current = db.one("PRAGMA user_version")[0]
    if current > VERSION:
        raise AppError("La base des comptes a été créée par une version plus récente de "
                       "SchoolManager. Installez la dernière version du logiciel.")
    if current >= VERSION:
        return
    script = SCHEMA if current == 0 else UPGRADE_2
    try:
        db.conn.executescript(f"BEGIN;\n{script}\nPRAGMA user_version={VERSION};\nCOMMIT;")
    except Exception:
        if db.conn.in_transaction:
            db.conn.execute("ROLLBACK")
        raise


def mirror_users(accounts_db, school_db) -> None:
    """Recopie les comptes dans la base de l'école, pour la traçabilité des opérations
    (paiements encaissés par, écritures créées par) sans jamais supprimer un ancien compte.

    Un compte supprimé est archivé (identifiant libéré, historique conservé) ; deux comptes
    qui échangent leurs identifiants ne provoquent plus de conflit UNIQUE."""
    columns = ", ".join(_COLUMNS)
    updates = ", ".join(f"{name}=excluded.{name}" for name in _COLUMNS if name != "id")
    rows = [tuple(row[name] for name in _COLUMNS)
            for row in accounts_db.all(f"SELECT {columns} FROM users")]
    known = {row[0]: row[1] for row in rows}                       # id -> identifiant courant
    with school_db.transaction():
        for old in school_db.all("SELECT id, username FROM users"):
            if old["username"].startswith("~"):
                if old["id"] in known:                              # compte revenu : remis à jour ci-dessous
                    school_db.execute("UPDATE users SET username=? WHERE id=?",
                                      (f"~tmp{old['id']}", old["id"]))
                continue
            if old["id"] not in known:                              # compte supprimé -> archivé
                school_db.execute(
                    "UPDATE users SET username=?, is_active=0 WHERE id=?",
                    (f"~{old['id']}~{old['username']}"[:50], old["id"]))
            elif old["username"] != known[old["id"]]:               # renommé : libère l'ancien nom
                school_db.execute("UPDATE users SET username=? WHERE id=?",
                                  (f"~tmp{old['id']}", old["id"]))
        school_db.executemany(
            f"INSERT INTO users ({columns}) VALUES ({','.join('?' * len(_COLUMNS))}) "
            f"ON CONFLICT(id) DO UPDATE SET {updates}", rows)
