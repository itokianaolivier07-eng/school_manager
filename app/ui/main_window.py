from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QListWidget, QMainWindow, QMessageBox, QStackedWidget,
                             QWidget)

from app.core.permissions import ROLE_LABELS
from app.ui import views
from app.ui.dialogs import ChangePasswordDialog
from app.ui.grades_view import GradesView
from app.ui.utils import handle_error


class MainWindow(QMainWindow):
    def __init__(self, services, ctx):
        super().__init__()
        self.sv, self.ctx = services, ctx
        self.relogin = False
        user = ctx.session.user
        self.setWindowTitle("Gestion d'école")
        self.resize(1150, 700)
        self.statusBar().showMessage(f"{user.full_name} — {ROLE_LABELS.get(user.role, user.role)}")

        pages = [("Élèves", "students.read", lambda: views.students_view(services, ctx)),
                 ("Enseignants", "teachers.read", lambda: views.teachers_view(services, ctx)),
                 ("Classes", "classes.read", lambda: views.classes_view(services, ctx)),
                 ("Matières", "subjects.read", lambda: views.subjects_view(services, ctx)),
                 ("Notes", "grades.read", lambda: GradesView(services, ctx)),
                 ("Utilisateurs", "users.manage", lambda: views.users_view(services, ctx)),
                 ("Journal d'audit", "audit.read", lambda: views.audit_view(services, ctx))]
        self.nav, self.stack = QListWidget(), QStackedWidget()
        self.nav.setFixedWidth(190)
        for title, perm, factory in pages:
            if ctx.session.can(perm):        # le menu n'affiche que ce que le rôle autorise
                self.nav.addItem(title)
                self.stack.addWidget(factory())
        self.nav.currentRowChanged.connect(self._on_page)
        central = QWidget()
        lay = QHBoxLayout(central)
        lay.addWidget(self.nav)
        lay.addWidget(self.stack, 1)
        self.setCentralWidget(central)
        self.nav.setCurrentRow(0)

        menu = self.menuBar().addMenu("Compte")
        for label, slot in (("Changer le mot de passe…", self.change_password), ("Se déconnecter", self.logout)):
            act = QAction(label, self)
            act.triggered.connect(slot)
            menu.addAction(act)
        if ctx.session.can("backup.run"):
            act = QAction("Sauvegarder la base", self)
            act.triggered.connect(self.backup)
            self.menuBar().addMenu("Données").addAction(act)

        self.idle = QTimer(self)             # contrôle d'inactivité
        self.idle.setInterval(10_000)
        self.idle.timeout.connect(self._check_idle)
        self.idle.start()

    def _on_page(self, i):
        w = self.stack.widget(i)
        self.stack.setCurrentIndex(i)
        if w is not None and hasattr(w, "refresh"):
            w.refresh()

    def change_password(self):
        ChangePasswordDialog(self.sv.auth).exec()

    def backup(self):
        try:
            QMessageBox.information(self, "Sauvegarde", f"Sauvegarde créée :\n{self.sv.backup.backup()}")
        except Exception as e:
            handle_error(self, e)

    def _check_idle(self):
        if self.ctx.session.expired:
            self.force_logout("Session expirée par inactivité.")

    def force_logout(self, message=None):
        if self.relogin:
            return
        self.sv.auth.logout("session_timeout")
        if message:
            QMessageBox.information(self, "Session", message)
        self.relogin = True
        self.close()

    def logout(self):
        self.sv.auth.logout()
        self.relogin = True
        self.close()

    def closeEvent(self, event):
        self.idle.stop()
        if self.ctx.session.user:
            self.sv.auth.logout()
        super().closeEvent(event)
