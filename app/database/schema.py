"""Migrations versionnées (PRAGMA user_version)."""
import logging
import sqlite3

from app.database.migration2 import MIGRATION_2
from app.database.migration3 import MIGRATION_3
from app.database.migration4 import MIGRATION_4
from app.database.migration5 import MIGRATION_5
from app.database.migration6 import MIGRATION_6
from app.database.migration7 import MIGRATION_7
from app.database.migration8 import MIGRATION_8
from app.database.migration9 import MIGRATION_9
from app.database.migration10 import MIGRATION_10
from app.database.migration11 import MIGRATION_11
from app.database.migration12 import MIGRATION_12
from app.database.migration13 import MIGRATION_13
from app.database.migration14 import MIGRATION_14

log = logging.getLogger(__name__)

MIGRATION_1 = """
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

CREATE TABLE teachers (
    id INTEGER PRIMARY KEY,
    employee_no TEXT NOT NULL UNIQUE,
    first_name TEXT NOT NULL COLLATE NOCASE,
    last_name TEXT NOT NULL COLLATE NOCASE,
    email TEXT UNIQUE,
    phone TEXT,
    speciality TEXT,
    hire_date TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_teachers_name ON teachers(last_name, first_name);

CREATE TABLE classes (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    level TEXT,
    school_year TEXT NOT NULL,
    main_teacher_id INTEGER REFERENCES teachers(id) ON DELETE SET NULL
);

CREATE TABLE subjects (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL COLLATE NOCASE,
    coefficient REAL NOT NULL DEFAULT 1 CHECK(coefficient > 0 AND coefficient <= 20),
    teacher_id INTEGER REFERENCES teachers(id) ON DELETE SET NULL
);

CREATE TABLE students (
    id INTEGER PRIMARY KEY,
    matricule TEXT NOT NULL UNIQUE,
    first_name TEXT NOT NULL COLLATE NOCASE,
    last_name TEXT NOT NULL COLLATE NOCASE,
    birth_date TEXT NOT NULL,
    gender TEXT CHECK(gender IN ('M','F')),
    email TEXT,
    phone TEXT,
    address TEXT,
    class_id INTEGER REFERENCES classes(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','suspended','graduated','left')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_students_name ON students(last_name, first_name);
CREATE INDEX idx_students_first ON students(first_name);
CREATE INDEX idx_students_class ON students(class_id);
CREATE INDEX idx_students_status ON students(status);
CREATE TRIGGER trg_students_updated AFTER UPDATE ON students FOR EACH ROW
BEGIN UPDATE students SET updated_at = datetime('now') WHERE id = NEW.id; END;

CREATE TABLE grades (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    term INTEGER NOT NULL CHECK(term BETWEEN 1 AND 3),
    value REAL NOT NULL CHECK(value BETWEEN 0 AND 20),
    comment TEXT,
    graded_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    graded_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(student_id, subject_id, term)
);
CREATE INDEX idx_grades_subject_term ON grades(subject_id, term);

"""

MIGRATIONS = [(1, MIGRATION_1), (2, MIGRATION_2), (3, MIGRATION_3), (4, MIGRATION_4),
              (5, MIGRATION_5), (6, MIGRATION_6), (7, MIGRATION_7), (8, MIGRATION_8),
              (9, MIGRATION_9), (10, MIGRATION_10), (11, MIGRATION_11),
              (12, MIGRATION_12), (13, MIGRATION_13), (14, MIGRATION_14)]


def migrate(db) -> None:
    current = db.one("PRAGMA user_version")[0]
    for version, sql in MIGRATIONS:
        if version <= current:
            continue
        log.info("Migration vers la version %s", version)
        try:
            if version == 12:
                db.conn.execute("PRAGMA foreign_keys=OFF")
                db.conn.execute("BEGIN")
                statement = ""
                for line in sql.splitlines():
                    statement += line + "\n"
                    if sqlite3.complete_statement(statement):
                        db.conn.execute(statement)
                        statement = ""
                if statement.strip():
                    raise RuntimeError(f"Migration {version} contient une instruction incomplète.")
                violations = db.conn.execute("PRAGMA foreign_key_check").fetchall()
                if violations:
                    raise RuntimeError(f"Violations de clés étrangères après migration : {violations}")
                db.conn.execute(f"PRAGMA user_version={version}")
                db.conn.execute("COMMIT")
            else:
                db.conn.executescript(f"BEGIN;\n{sql}\nPRAGMA user_version={version};\nCOMMIT;")
        except Exception:
            if db.conn.in_transaction:
                db.conn.execute("ROLLBACK")
            raise
        finally:
            if version == 12:
                db.conn.execute("PRAGMA foreign_keys=ON")
