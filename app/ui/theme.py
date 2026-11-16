"""Feuille de style globale en mode clair."""
import re

PALETTE = {
        "main": "#f5f6fb", "card": "#ffffff", "sidebar": "#ffffff",
        "usercard": "#f8fafc", "hover": "#f1f5f9", "active": "#eef2ff",
        "toolbar": "#ffffff", "border": "#e2e8f0", "border_soft": "#eef0f6",
        "text": "#1e293b", "secondary": "#475569", "muted": "#64748b",
        "faint": "#94a3b8", "nav": "#475569", "nav_active": "#3730a3",
        "accent": "#4f46e5", "accent_hover": "#4338ca", "accent_pressed": "#3730a3",
        "accent_light": "#eef2ff", "accent_lighter": "#e0e7ff",
        "accent_border": "#c7d2fe", "title": "#1e1b4b",
        "danger": "#b91c1c", "danger_bg": "#fef2f2", "danger_border": "#fecaca",
        "logout_hover": "#fee2e2", "input_border": "#cbd5e1",
        "selection": "#c7d2fe", "selection_text": "#1e1b4b",
        "table_alt": "#f8f9ff", "table_sel": "#e0e7ff",
        "header": "#eef2ff", "header_text": "#3730a3", "scrollbar": "#cbd5e1",
        "row_view_bg": "#eef2ff", "row_view_text": "#4338ca",
        "row_view_border": "#c7d2fe", "row_view_hover": "#c7d2fe",
        "row_edit_bg": "#ecfdf5", "row_edit_text": "#047857",
        "row_edit_border": "#a7f3d0", "row_edit_hover": "#a7f3d0",
        "on_accent": "#ffffff", "nav_icon_idle": "#475569",
        "nav_icon_active": "#3730a3",
        "positive": "#047857", "negative": "#b91c1c", "warning": "#b45309",
        "series_1": "#4f46e5", "series_2": "#f97316",
        "status_paid_bg": "#dcfce7", "status_paid_text": "#166534",
        "status_partial_bg": "#fef3c7", "status_partial_text": "#92400e",
        "status_due_bg": "#fee2e2", "status_due_text": "#991b1b",
        "status_free_bg": "#f1f5f9", "status_free_text": "#475569",
}

_TEMPLATE = """
* { font-family: "Inter", "Segoe UI", "Noto Sans", "Ubuntu", sans-serif; font-size: 10.5pt; }
QMainWindow, QDialog, QWidget#page { background: %(main)s; }
QDialog#appDialog { background: %(main)s; }
QFrame#dialogCard { background: %(card)s; border: 1px solid %(border)s; border-radius: 16px; }
QLabel { color: %(text)s; background: transparent; }
QLabel#pageTitle { font-size: 20pt; font-weight: 700; color: %(title)s; }
QLabel#dialogTitle { font-size: 19pt; font-weight: 700; color: %(title)s; padding: 4px 0; }
QLabel#dialogSubtitle { color: %(muted)s; padding-bottom: 8px; }
QLabel#dialogError { color: %(danger)s; background: %(danger_bg)s; border: 1px solid %(danger_border)s;
                     border-radius: 8px; padding: 8px; }
QLabel#muted { color: %(muted)s; }
QLabel#error { color: %(danger)s; }
QLabel#resultInfo { color: %(muted)s; font-size: 9.5pt; }

QListWidget#results { background: %(card)s; border: 1px solid %(border)s; border-radius: 10px; padding: 4px; }
QListWidget#results::item { padding: 8px 12px; border-radius: 8px; color: %(text)s; }
QListWidget#results::item:selected { background: %(active)s; color: %(nav_active)s; }

QFrame#sidebar {
    background: %(sidebar)s;
    border: none;
    border-right: 1px solid %(border_soft)s;
    max-width: 252px;
    min-width: 252px;
}
QLabel#brandName { font-size: 15pt; font-weight: 800; color: %(accent)s; letter-spacing: -0.5px; }
QLabel#navSection {
    color: %(faint)s; font-size: 8.5pt; font-weight: 700;
    padding: 14px 14px 4px 14px; letter-spacing: 1.2px;
}
QPushButton#navButton {
    text-align: left;
    background: transparent;
    color: %(nav)s;
    border: none;
    border-radius: 10px;
    padding: 10px 14px;
    margin: 1px 0;
    font-weight: 600;
    font-size: 10.5pt;
}
QPushButton#navButton:hover { background: %(hover)s; color: %(text)s; }
QPushButton#navButton:checked {
    background: %(active)s;
    color: %(nav_active)s;
    font-weight: 700;
}
QFrame#userCard {
    background: %(usercard)s;
    border: 1px solid %(border)s;
    border-radius: 14px;
}
QFrame#userCard:hover { background: %(hover)s; }
QLabel#userName { color: %(text)s; font-weight: 700; font-size: 10.5pt; }
QLabel#userRole { color: %(muted)s; font-size: 9pt; }
QPushButton#logoutBtn {
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 4px;
}
QPushButton#logoutBtn:hover { background: %(logout_hover)s; }
QPushButton { background: %(accent)s; color: %(on_accent)s; border: none; border-radius: 9px;
              padding: 8px 18px; font-weight: 600; }
QPushButton:hover { background: %(accent_hover)s; }
QPushButton:pressed { background: %(accent_pressed)s; }
QPushButton:disabled { background: %(border)s; color: %(muted)s; }

QPushButton#primaryButton { background: %(accent)s; color: %(on_accent)s; }
QPushButton#primaryButton:hover { background: %(accent_hover)s; }
QPushButton#secondaryButton { background: %(accent_lighter)s; color: %(nav_active)s; }
QPushButton#secondaryButton:hover { background: %(accent_border)s; }

QPushButton#rowViewBtn {
    background: %(row_view_bg)s; color: %(row_view_text)s; border: 1px solid %(row_view_border)s;
    border-radius: 7px; padding: 4px 12px; font-weight: 600; font-size: 9.5pt;
}
QPushButton#rowViewBtn:hover { background: %(row_view_hover)s; }
QPushButton#rowEditBtn {
    background: %(row_edit_bg)s; color: %(row_edit_text)s; border: 1px solid %(row_edit_border)s;
    border-radius: 7px; padding: 4px 12px; font-weight: 600; font-size: 9.5pt;
}
QPushButton#rowEditBtn:hover { background: %(row_edit_hover)s; }
QPushButton#rowDeleteBtn {
    background: %(danger_bg)s; color: %(danger)s; border: 1px solid %(danger_border)s;
    border-radius: 7px; padding: 4px 12px; font-weight: 600; font-size: 9.5pt;
}
QPushButton#rowDeleteBtn:hover { background: %(danger_border)s; }

QWidget#actionsCell { background: transparent; }

QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox {
    color: %(text)s; background: %(card)s; border: 1px solid %(input_border)s; border-radius: 9px; padding: 7px 10px;
    selection-background-color: %(selection)s; selection-color: %(selection_text)s; min-height: 20px; }
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QDoubleSpinBox:focus { border: 2px solid %(accent)s; }
QLineEdit#searchField { padding: 9px 14px; font-size: 10.5pt; }
QLineEdit#loginUser, QLineEdit#loginPassword { min-height: 28px; }
QComboBox::drop-down, QDateEdit::drop-down { border: none; width: 26px; }
QComboBox QAbstractItemView { color: %(text)s; background: %(card)s; border: 1px solid %(input_border)s;
                              selection-background-color: %(accent_lighter)s; selection-color: %(selection_text)s; }

QTableView, QTableWidget, QListWidget#results { background: %(card)s; alternate-background-color: %(table_alt)s;
    color: %(text)s; border: 1px solid %(border)s; border-radius: 12px; gridline-color: transparent;
    selection-background-color: %(table_sel)s; selection-color: %(selection_text)s; }
QTableView::item, QTableWidget::item { color: %(text)s; padding: 6px; }
QHeaderView::section { background: %(header)s; color: %(header_text)s; padding: 10px; border: none; font-weight: 700; }
QTableCornerButton::section { background: %(header)s; border: none; }

QTabWidget::pane { border: none; margin-top: 8px; }
QTabBar::tab { background: transparent; color: %(muted)s; padding: 9px 18px; margin-right: 4px;
               border-radius: 9px; font-weight: 600; }
QTabBar::tab:selected { background: %(card)s; color: %(accent)s; }
QTabBar::tab:hover:!selected { background: %(accent_lighter)s; }

QFrame#card { background: %(card)s; border: 1px solid %(border)s; border-radius: 14px; }
QLabel#cardValue { font-size: 22pt; font-weight: 700; color: %(accent)s; }
QLabel#cardTitle { color: %(muted)s; font-weight: 600; }
QLabel#cardHint { color: %(faint)s; font-size: 9pt; }
QLabel#sectionTitle { font-size: 14pt; font-weight: 700; color: %(title)s; }
QLabel#chartTitle { font-size: 11.5pt; font-weight: 700; color: %(title)s; }
QLabel#detailLabel { color: %(secondary)s; font-weight: 600; }
QLabel#detailValue { color: %(text)s; font-weight: 700; }
QLabel#detailTotal { font-size: 15pt; font-weight: 700; }
QFrame#detailSeparator { color: %(border)s; background: %(border)s; max-height: 1px; border: none; }

QMenuBar { background: %(toolbar)s; border-bottom: 1px solid %(border)s; }
QMenuBar::item { padding: 6px 12px; border-radius: 6px; }
QMenuBar::item:selected { background: %(active)s; }
QMenu { background: %(card)s; border: 1px solid %(border)s; border-radius: 10px; padding: 6px; }
QMenu::item { padding: 7px 18px; border-radius: 6px; }
QMenu::item:selected { background: %(active)s; color: %(nav_active)s; }
QStatusBar { background: %(toolbar)s; color: %(muted)s; border-top: 1px solid %(border)s; }
QLabel#userInfo { color: %(muted)s; padding: 4px; }
QToolBar#topMenuBar { background: %(toolbar)s; border: none; border-bottom: 1px solid %(border_soft)s;
                      spacing: 6px; padding: 6px 12px; }
QToolButton#statusMenuButton { background: transparent; color: %(secondary)s; border: none;
                               border-radius: 8px; padding: 6px 14px; font-weight: 600; }
QToolButton#statusMenuButton:hover, QToolButton#statusMenuButton::menu-button:hover {
    background: %(hover)s; color: %(text)s; }
QToolButton#statusMenuButton::menu-indicator { image: none; }
QMessageBox { background: %(card)s; }
QScrollBar:vertical { background: transparent; width: 10px; }
QScrollBar::handle:vertical { background: %(scrollbar)s; border-radius: 5px; min-height: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
"""

def current_palette() -> dict:
    return PALETTE


_PLACEHOLDER = re.compile(r"%\((\w+)\)s")


def build_stylesheet() -> str:
    return _PLACEHOLDER.sub(lambda match: PALETTE[match.group(1)], _TEMPLATE)


def apply_theme(app) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(build_stylesheet())
