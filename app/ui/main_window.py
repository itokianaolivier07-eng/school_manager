from PyQt6.QtCore import QSize, Qt, QTimer
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
                             QMenu, QSizePolicy, QStackedWidget, QToolBar, QToolButton, QVBoxLayout, QWidget)

from app.core.permissions import ROLE_LABELS
from app.ui import views
from app.ui.dashboard_view import DashboardView
from app.ui.dialogs import ChangePasswordDialog
from app.ui.fees_view import FeesView
from app.ui.icons import icon_moon, icon_sun
from app.ui.sidebar import Sidebar
from app.ui import theme
from app.ui.toast import show_toast
from app.ui.utils import handle_error


class MainWindow(QMainWindow):
    def __init__(self, services, ctx):
        super().__init__()
        self.sv, self.ctx = services, ctx
        self.relogin = False
        user = ctx.session.user
        self.setWindowTitle("Gestion d'école")
        self.resize(1280, 780)
        self._center_on_primary_screen()
        self.user_info = QLabel(f"{user.full_name} - {ROLE_LABELS.get(user.role, user.role)}")
        self.user_info.setObjectName("userInfo")
        self.user_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.statusBar().addWidget(self.user_info, 1)
        self.top_toolbar = QToolBar()
        self.top_toolbar.setObjectName("topMenuBar")
        self.top_toolbar.setMovable(False)
        self.top_toolbar.setFloatable(False)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.top_toolbar)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.top_toolbar.addWidget(spacer)

        self.theme_btn = QToolButton()
        self.theme_btn.setObjectName("themeToggleBtn")
        self.theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme_btn.setIconSize(QSize(20, 20))
        self.theme_btn.clicked.connect(self.toggle_theme)
        self._update_theme_button()
        self.top_toolbar.addWidget(self.theme_btn)

        pages = [
            ("Tableau de bord", "Tableau de bord", "dashboard.read", lambda: DashboardView(services, ctx)),
            ("Élèves", "Élèves", "students.read",
             lambda: views.students_view(services, ctx, self.refresh_data_views)),
            ("Employés", "Employés", "teachers.read",
             lambda: views.teachers_view(services, ctx, self.refresh_data_views)),
            ("Classes", "Classes", "classes.read",
             lambda: views.classes_view(services, ctx, self.refresh_data_views)),
            ("Pointage", "Pointage", "attendance.read",
             lambda: views.attendance_view(services, ctx, self.refresh_data_views)),
            ("Salaires", "Salaires", "salaries.read",
             lambda: views.salaries_view(services, ctx, self.refresh_data_views)),
            ("Écolages", "Écolages", "payments.read",
             lambda: FeesView(services, ctx, self.refresh_data_views)),
            ("Charges", "Charges", "expenses.read",
             lambda: views.expenses_view(services, ctx, self.refresh_data_views)),
            ("Utilisateurs", "Utilisateurs", "users.manage",
             lambda: views.users_view(services, ctx, self.refresh_data_views)),
        ]
        authorized = [(label, title, perm, factory) for label, title, perm, factory in pages
                      if ctx.session.can(perm)]
        self.titles = [title for _, title, _, _ in authorized]
        self.stack = QStackedWidget()
        for _, _, _, factory in authorized:
            self.stack.addWidget(factory())

        self.sidebar = Sidebar(authorized, user, on_logout=self.logout)
        self.sidebar.page_requested.connect(self._on_page)

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
        lay.addWidget(self.sidebar)
        lay.addWidget(right, 1)
        self.setCentralWidget(central)
        self._on_page(0)

        account_menu = QMenu("Compte", self)
        for label, slot in (("Changer le mot de passe…", self.change_password), ("Se déconnecter", self.logout)):
            act = QAction(label, self)
            act.triggered.connect(slot)
            account_menu.addAction(act)
        self._add_toolbar_menu("Compte", account_menu)
        if ctx.session.can("backup.run"):
            act = QAction("Sauvegarder la base", self)
            act.triggered.connect(self.backup)
            data_menu = QMenu("Données", self)
            data_menu.addAction(act)
            self._add_toolbar_menu("Données", data_menu)

        self.idle = QTimer(self)
        self.idle.setInterval(10_000)
        self.idle.timeout.connect(self._check_idle)
        self.idle.start()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._center_on_primary_screen)

    def _center_on_primary_screen(self):
        screen = QApplication.primaryScreen()
        if screen is not None:
            frame = self.frameGeometry()
            frame.moveCenter(screen.availableGeometry().center())
            self.move(frame.topLeft())

    def _add_toolbar_menu(self, label, menu):
        menu.setObjectName("navigationMenu")
        button = QToolButton(self.top_toolbar)
        button.setObjectName("statusMenuButton")
        button.setText(label)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setMenu(menu)
        self.top_toolbar.addWidget(button)

    def _update_theme_button(self):
        palette = theme.current_palette()
        if theme.current_mode() == "dark":
            self.theme_btn.setIcon(icon_sun(palette["secondary"]))
            self.theme_btn.setToolTip("Passer au mode clair")
        else:
            self.theme_btn.setIcon(icon_moon(palette["secondary"]))
            self.theme_btn.setToolTip("Passer au mode sombre")

    def toggle_theme(self):
        new_mode = "dark" if theme.current_mode() == "light" else "light"
        theme.set_theme_mode(new_mode)
        theme.apply_theme(QApplication.instance(), new_mode)
        self._update_theme_button()
        self.sidebar.apply_theme()

    def _on_page(self, i):
        self.sidebar.set_current(i)
        w = self.stack.widget(i)
        self.stack.setCurrentIndex(i)
        self.page_title.setText(self.titles[i] if 0 <= i < len(self.titles) else "")
        if w is not None and hasattr(w, "refresh"):
            w.refresh()

    def refresh_data_views(self):
        for index in range(self.stack.count()):
            widget = self.stack.widget(index)
            refresh_filters = getattr(widget, "refresh_filters", None)
            if refresh_filters:
                refresh_filters()
            refresh = getattr(widget, "refresh", None)
            if refresh:
                refresh()

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
        self.sv.auth.logout()
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
