"""Contrôle d'accès par rôles (RBAC)."""
from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    SECRETARY = "secretary"
    TEACHER = "teacher"


ROLE_LABELS = {"admin": "Administrateur", "secretary": "Secrétariat", "teacher": "Employé"}

_ALL = {
    "dashboard.read",
    "students.read", "students.write", "students.delete", "students.import", "students.export",
    "teachers.read", "teachers.write", "teachers.delete",
    "classes.read", "classes.write", "classes.delete",
    "attendance.read", "attendance.write", "attendance.delete",
    "salaries.read", "salaries.write", "salaries.delete",
    "fees.read", "fees.write", "fees.delete",
    "payments.read", "payments.write", "payments.cancel", "payments.export",
    "users.manage", "audit.read", "backup.run",
}

ROLE_PERMISSIONS = {
    "admin": _ALL,
    "secretary": {
        "dashboard.read",
        "students.read", "students.write", "students.delete", "students.import", "students.export",
        "teachers.read", "teachers.write",
        "classes.read", "classes.write",
        "attendance.read", "attendance.write",
        "salaries.read",
        "fees.read", "payments.read", "payments.write", "payments.cancel", "payments.export",
    },
    "teacher": {
        "dashboard.read",
        "students.read", "classes.read",
        "attendance.read",
    },
}
