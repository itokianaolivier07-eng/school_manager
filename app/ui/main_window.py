from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QListWidget, QMainWindow, QMessageBox,
                             QStackedWidget, QVBoxLayout, QWidget)

from app.core.permissions import ROLE_LABELS
from app.ui import views
from app.ui.dashboard_view import DashboardView
from app.ui.dialogs import ChangePasswordDialog
from app.ui.fees_view import FeesView
from app.ui.grades_view import GradesView
from app.ui.toast import show_toast
from app.ui.utils import handle_error


class MainWindow(QMainWindow):
    def __init__(self, services, ctx):
        super().__init__()
        self.sv, self.ctx = services, ctx
        self.relogin = False
        user = ctx.session.user
        self.setWindowTitle("Gestion d'école")
        self.resize(1250, 760)
        self.statusBar().showMessage(f"{user.full_name} — {ROLE_LABELS.get(user.role, user.role)}")

        pages = [("Tableau de bord", "Tableau de bord", "dashboard.read", lambda: DashboardView(services, ctx)),
                 ("Élèves", "Élèves", "students.read", lambda: views.students_view(services, ctx)),
                 ("Enseignants", "Enseignants", "teachers.read", lambda: views.teachers_view(services, ctx)),
                 ("Classes", "Classes", "classes.read", lambda: views.classes_view(services, ctx)),
                 ("Matières", "Matières", "subjects.read", lambda: views.subjects_view(services, ctx)),
                 ("Notes", "Notes et résultats", "grades.read", lambda: GradesView(services, ctx)),
                 ("Écolages", "Écolages", "payments.read", lambda: FeesView(services, ctx)),
                 ("Utilisateurs", "Utilisateurs", "users.manage", lambda: views.users_view(services, ctx)),
                 ("Journal d'audit", "Journal d'audit", "audit.read", lambda: views.audit_view(services, ctx))]
        self.nav, self.stack, self.titles = QListWidget(), QStackedWidget(), []
        self.nav.setObjectName("nav")
        self.nav.setFixedWidth(220)
        for label, title, perm, factory in pages:
            if ctx.session.can(perm):        # le menu n'affiche que ce que le rôle autorise
                self.nav.addItem(label)
                self.titles.append(title)
                self.stack.addWidget(factory())
        self.page_title = QLabel()
        self.page_title.setObjectName("pageTitle")
        right = QWidget()
        right.setObjectName("page")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(24, 18, 24, 18)
        rl.addWidget(self.page_title)
        rl.addWidget(self.stack, 1)
        central = QWidget()
        lay = QHBoxLayout(central)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.nav)
        lay.addWidget(right, 1)
        self.setCentralWidget(central)
        self.nav.currentRowChanged.connect(self._on_page)
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
        self.page_title.setText(self.titles[i] if 0 <= i < len(self.titles) else "")
        if w is not None and hasattr(w, "refresh"):
            w.refresh()

    def change_password(self):
        if ChangePasswordDialog(self.sv.auth).exec() == QDialog.DialogCode.Accepted:
            show_toast(self, "Mot de passe modifié")

    def backup(self):
        try:
            path = self.sv.backup.backup()
            QMessageBox.information(self, "Sauvegarde", f"Sauvegarde créée :\n{path}")
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
