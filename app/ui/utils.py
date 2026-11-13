import logging

from PyQt6.QtWidgets import QMessageBox

from app.core.exceptions import AppError, AuthenticationError

log = logging.getLogger(__name__)


def handle_error(parent, exc: Exception) -> None:
    if isinstance(exc, AuthenticationError):
        QMessageBox.warning(parent, "Session", str(exc))
        win = parent.window() if parent else None
        if win is not None and hasattr(win, "force_logout"):
            win.force_logout()
    elif isinstance(exc, AppError):
        QMessageBox.warning(parent, "Information", str(exc))
    else:
        log.exception("Erreur inattendue", exc_info=exc)
        QMessageBox.critical(parent, "Erreur", f"{type(exc).__name__}: {exc}")


LABELS = {
    "gender": {"M": "Masculin", "F": "Féminin"},
    "status": {"active": "Actif", "suspended": "Suspendu", "graduated": "Diplômé", "left": "Parti"},
    "role": {"admin": "Administrateur", "secretary": "Secrétariat", "teacher": "Employé"},
    "is_active": {1: "Actif", 0: "Inactif"},
    "attendance_status": {"present": "Présent", "absent": "Absent", "late": "En retard"},
}
