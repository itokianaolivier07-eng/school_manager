import os
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
import sys
from PyQt6.QtCore import QEvent, QObject
from PyQt6.QtWidgets import QApplication, QDialog

from app import config
from app.core.context import AppContext
from app.core.logging_setup import setup_logging
from app.core.session import Session
from app.database.connection import Database
from app.database.schema import migrate
from app.services import Services
from app.ui.dialogs import ChangePasswordDialog, LoginDialog, SetupDialog
from app.ui.main_window import MainWindow


class ActivityFilter(QObject):
    """Remet à zéro le compteur d'inactivité à chaque clic ou touche."""

    def __init__(self, session):
        super().__init__()
        self.session = session

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.KeyPress):
            self.session.touch()
        return False


def main() -> int:
    config.ensure_dirs()
    setup_logging()
    db = Database(config.DB_PATH)
    migrate(db)
    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    session = Session(config.SESSION_TIMEOUT_SECONDS)
    ctx = AppContext(db, session)
    services = Services(ctx)
    activity = ActivityFilter(session)
    app.installEventFilter(activity)

    if not services.auth.has_users() and SetupDialog(services.auth).exec() != QDialog.DialogCode.Accepted:
        return 0
    while True:
        if LoginDialog(services.auth).exec() != QDialog.DialogCode.Accepted:
            break
        if session.user.must_change_password and \
                ChangePasswordDialog(services.auth, forced=True).exec() != QDialog.DialogCode.Accepted:
            services.auth.logout()
            continue
        window = MainWindow(services, ctx)
        window.show()
        app.exec()
        if not window.relogin:
            break
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
