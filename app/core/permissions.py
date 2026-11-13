"""Contrôle d'accès par rôles (RBAC)."""
from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    SECRETARY = "secretary"
    TEACHER = "teacher"


ROLE_LABELS = {"admin": "Administrateur", "secretary": "Secrétariat", "teacher": "Enseignant"}

_ALL = {
    "dashboard.read",
    "students.read", "students.write", "students.delete", "students.import", "students.export",
    "teachers.read", "teachers.write", "teachers.delete",
    "classes.read", "classes.write", "classes.delete",
    "subjects.read", "subjects.write", "subjects.delete",
    "grades.read", "grades.write",
    "fees.read", "fees.write", "fees.delete",
    "payments.read", "payments.write", "payments.cancel",
    "users.manage", "audit.read", "backup.run",
}

ROLE_PERMISSIONS = {
    "admin": _ALL,
    "secretary": {
        "dashboard.read",
        "students.read", "students.write", "students.delete", "students.import", "students.export",
        "teachers.read", "classes.read", "classes.write", "subjects.read", "grades.read",
        "fees.read", "payments.read", "payments.write", "payments.cancel",
    },
    "teacher": {
        "dashboard.read",
        "students.read", "classes.read", "subjects.read", "grades.read", "grades.write",
    },
}
