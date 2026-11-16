import logging
import os
import sys

if sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

from PyQt6.QtCore import QEvent, QObject
from PyQt6.QtWidgets import QApplication, QDialog, QMessageBox

from app import config
from app.core.context import AppContext
from app.core.logging_setup import setup_logging
from app.core.session import Session
from app.database.accounts import migrate_accounts, mirror_users
from app.database.connection import Database
from app.database.schema import MIGRATIONS, migrate
from app.services import Services
from app.services.backup_service import BackupService
from app.services.auth_service import AuthService
from app.ui.dialogs import ChangePasswordDialog, LoginDialog, SchoolDialog, SetupDialog
from app.ui.main_window import MainWindow
from app.ui.theme import apply_theme


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
    db = accounts = None
    try:
        config.ensure_root()
        setup_logging()
        app = QApplication(sys.argv)
        app.setApplicationName(config.APP_NAME)
        apply_theme(app)

        # Les comptes vivent dans leur propre base : le login précède le choix de l'école.
        accounts = Database(config.ACCOUNTS_PATH)
        migrate_accounts(accounts)
        session = Session(config.SESSION_TIMEOUT_SECONDS)
        auth = AuthService(AppContext(None, session, accounts))
        app.installEventFilter(ActivityFilter(session))

        if not auth.has_users() and SetupDialog(auth).exec() != QDialog.DialogCode.Accepted:
            return 0
        while True:
            if LoginDialog(auth).exec() != QDialog.DialogCode.Accepted:
                break
            if session.user.must_change_password and \
                    ChangePasswordDialog(auth, forced=True).exec() != QDialog.DialogCode.Accepted:
                auth.logout()
                continue
            if SchoolDialog().exec() != QDialog.DialogCode.Accepted:
                auth.logout()
                continue
            config.ensure_dirs()
            if db is not None:
                db.close()
            db = Database(config.DB_PATH)
            current_version = db.one("PRAGMA user_version")[0]
            ctx = AppContext(db, session, accounts)
            if 0 < current_version < MIGRATIONS[-1][0]:
                BackupService(ctx).backup_before_migration()
            migrate(db)
            mirror_users(accounts, db)
            try:
                BackupService(ctx).auto_backup()
            except Exception:
                logging.getLogger(__name__).warning("Sauvegarde automatique impossible", exc_info=True)
            window = MainWindow(Services(ctx), ctx)
            window.show()
            app.exec()
            if not window.relogin:
                break
    except Exception as exc:
        logging.getLogger(__name__).critical(
            "Échec au démarrage ou pendant l'exécution", exc_info=(type(exc), exc, exc.__traceback__))
        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(
            None, "Démarrage impossible",
            "L'application a rencontré une erreur et ne peut pas continuer. Consultez le journal.")
        return 1
    finally:
        for database in (db, accounts):
            if database is not None:
                database.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
