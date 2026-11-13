import logging

from PyQt6.QtWidgets import QMessageBox

from app.core.exceptions import AppError, AuthenticationError

log = logging.getLogger(__name__)


def handle_error(parent, exc: Exception) -> None:
    """Affiche les erreurs métier ; les erreurs inattendues sont journalisées sans fuite de détails."""
    if isinstance(exc, AuthenticationError):
        QMessageBox.warning(parent, "Session", str(exc))
        win = parent.window() if parent else None
        if win is not None and hasattr(win, "force_logout"):
            win.force_logout()
    elif isinstance(exc, AppError):
        QMessageBox.warning(parent, "Information", str(exc))
    else:
        log.exception("Erreur inattendue", exc_info=exc)
        QMessageBox.critical(parent, "Erreur", "Une erreur inattendue s'est produite (voir les logs).")


LABELS = {
    "gender": {"M": "Masculin", "F": "Féminin"},
    "status": {"active": "Actif", "suspended": "Suspendu", "graduated": "Diplômé", "left": "Parti"},
    "role": {"admin": "Administrateur", "secretary": "Secrétariat", "teacher": "Enseignant"},
    "is_active": {1: "Actif", 0: "Inactif"},
}
