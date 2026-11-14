"""Panneau de navigation latéral moderne avec icônes et carte utilisateur."""
from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
                             QSizePolicy, QVBoxLayout, QWidget)

from app.core.permissions import ROLE_LABELS
from app.ui.icons import NAV_ICONS, icon_logo, icon_logout
from app.ui import theme

GROUPS = [
    ("GÉNÉRAL", ("Tableau de bord",)),
    ("GESTION", ("Élèves", "Employés", "Classes", "Pointage", "Salaires", "Écolages", "Charges")),
    ("SYSTÈME", ("Utilisateurs",)),
]


def _avatar_pixmap(text, size=44, bg=None):
    from PyQt6.QtGui import QPixmap
    if bg is None:
        bg = theme.current_palette()["accent"]
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(bg))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(0, 0, size, size)
    p.setPen(QColor("white"))
    font = QFont()
    font.setPointSizeF(size * 0.38)
    font.setBold(True)
    p.setFont(font)
    p.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, text.upper())
    p.end()
    return pix


class NavButton(QPushButton):
    """Bouton de navigation avec icône et état actif."""

    def __init__(self, label, icon_func):
        super().__init__()
        self.label_text = label
        self._icon_func = icon_func
        self.setObjectName("navButton")
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIconSize(QSize(20, 20))
        self.setText(f"  {label}")
        self.set_active(False)

    def set_active(self, active: bool):
        self.setChecked(active)
        palette = theme.current_palette()
        color = palette["nav_icon_active"] if active else palette["nav_icon_idle"]
        self.setIcon(self._icon_func(color))


class Sidebar(QFrame):
    page_requested = pyqtSignal(int)
    logout_requested = pyqtSignal()

    def __init__(self, pages, user, on_logout=None):
        super().__init__()
        self.setObjectName("sidebar")
        self.user = user
        self._buttons = []

        if on_logout is not None:
            self.logout_requested.connect(on_logout)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 16)
        layout.setSpacing(6)

        # --- Logo + nom ---
        logo_row = QHBoxLayout()
        logo_row.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(icon_logo().pixmap(QSize(36, 36)))
        logo_row.addWidget(logo)
        name = QLabel("SchoolManager")
        name.setObjectName("brandName")
        logo_row.addWidget(name)
        logo_row.addStretch(1)
        layout.addLayout(logo_row)
        layout.addSpacing(8)

        # --- Zones de navigation ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent; border: none;")

        nav_host = QWidget()
        nav_host.setStyleSheet("background: transparent;")
        nav_layout = QVBoxLayout(nav_host)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(4)

        self._build_groups(nav_layout, pages)
        nav_layout.addStretch(1)
        scroll.setWidget(nav_host)
        layout.addWidget(scroll, 1)

        # --- Carte utilisateur ---
        layout.addWidget(self._build_user_card())

    def _build_groups(self, parent_layout, pages):
        index_by_label = {label: i for i, (label, _, _, _) in enumerate(pages)}
        for group_name, labels in GROUPS:
            visible = [label for label in labels if label in index_by_label]
            if not visible:
                continue
            section = QLabel(group_name)
            section.setObjectName("navSection")
            parent_layout.addWidget(section)
            parent_layout.addSpacing(2)
            for label in visible:
                btn = NavButton(label, NAV_ICONS.get(label, NAV_ICONS["Tableau de bord"]))
                btn.clicked.connect(lambda _=False, idx=index_by_label[label]: self.page_requested.emit(idx))
                self._buttons.append(btn)
                parent_layout.addWidget(btn)
            parent_layout.addSpacing(10)

    def _build_user_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("userCard")
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        row = QHBoxLayout(card)
        row.setContentsMargins(10, 10, 10, 10)
        row.setSpacing(10)

        avatar = QLabel()
        self._avatar_initials = (self.user.full_name.strip() or "?")[:2].upper()
        avatar.setPixmap(_avatar_pixmap(self._avatar_initials, 40))
        self._avatar_label = avatar
        row.addWidget(avatar)

        text_col = QVBoxLayout()
        text_col.setSpacing(0)
        name = QLabel(self.user.full_name)
        name.setObjectName("userName")
        role = QLabel(ROLE_LABELS.get(self.user.role, self.user.role))
        role.setObjectName("userRole")
        text_col.addWidget(name)
        text_col.addWidget(role)
        row.addLayout(text_col, 1)

        logout = QPushButton()
        logout.setObjectName("logoutBtn")
        palette = theme.current_palette()
        logout.setIcon(icon_logout(palette["muted"]))
        logout.setIconSize(QSize(18, 18))
        logout.setCursor(Qt.CursorShape.PointingHandCursor)
        logout.setToolTip("Se déconnecter")
        logout.clicked.connect(self.logout_requested.emit)
        self._logout_btn = logout
        row.addWidget(logout)
        return card

    def apply_theme(self):
        palette = theme.current_palette()
        self._avatar_label.setPixmap(_avatar_pixmap(self._avatar_initials, 40))
        self._logout_btn.setIcon(icon_logout(palette["muted"]))
        for button in self._buttons:
            button.set_active(button.isChecked())

    def set_current(self, index: int):
        for pos, button in enumerate(self._buttons):
            button.set_active(pos == index)
