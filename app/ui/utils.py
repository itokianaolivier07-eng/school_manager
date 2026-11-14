import logging

from PyQt6.QtGui import QIcon
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
        log.error("Erreur inattendue", exc_info=(type(exc), exc, exc.__traceback__))
        QMessageBox.critical(
            parent, "Erreur", "Une erreur inattendue est survenue. Elle a été enregistrée dans le journal.")


def ask_confirmation(parent, title: str, message: str,
                     confirm_text: str = "Oui", cancel_text: str = "Non") -> bool:
    dialog = QMessageBox(parent)
    dialog.setIcon(QMessageBox.Icon.Question)
    dialog.setWindowTitle(title)
    dialog.setText(message)
    confirm_button = dialog.addButton(confirm_text, QMessageBox.ButtonRole.AcceptRole)
    cancel_button = dialog.addButton(cancel_text, QMessageBox.ButtonRole.RejectRole)
    confirm_button.setIcon(QIcon())
    cancel_button.setIcon(QIcon())
    dialog.setDefaultButton(cancel_button)
    dialog.exec()
    return dialog.clickedButton() is confirm_button


LABELS = {
    "gender": {"M": "Masculin", "F": "Féminin"},
    "status": {"active": "Actif", "suspended": "Suspendu", "graduated": "Diplômé", "left": "Parti"},
    "role": {"admin": "Administrateur", "secretary": "Secrétariat", "teacher": "Employé"},
    "is_active": {1: "Actif", 0: "Inactif"},
    "attendance_status": {"present": "Présent", "absent": "Absent", "late": "En retard"},
}
