"""Contrôle d'accès par rôles (RBAC)."""
from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    SECRETARY = "secretary"
    TEACHER = "teacher"


ROLE_LABELS = {"admin": "Administrateur", "secretary": "Secrétariat", "teacher": "Enseignant"}

_ALL = {
    "students.read", "students.write", "students.delete", "students.import", "students.export",
    "teachers.read", "teachers.write", "teachers.delete",
    "classes.read", "classes.write", "classes.delete",
    "subjects.read", "subjects.write", "subjects.delete",
    "grades.read", "grades.write",
    "users.manage", "audit.read", "backup.run",
}

ROLE_PERMISSIONS = {
    "admin": _ALL,
    "secretary": {
        "students.read", "students.write", "students.delete", "students.import", "students.export",
        "teachers.read", "classes.read", "classes.write", "subjects.read", "grades.read",
    },
    "teacher": {
        "students.read", "classes.read", "subjects.read", "grades.read", "grades.write",
    },
}
