"""Feuille de style globale de l'application."""

STYLESHEET = """
* { font-family: "Inter", "Segoe UI", "Noto Sans", "Ubuntu", sans-serif; font-size: 10.5pt; }
QMainWindow, QDialog, QWidget#page { background: #f5f6fb; }
QLabel { color: #1e293b; background: transparent; }
QLabel#pageTitle { font-size: 20pt; font-weight: 700; color: #1e1b4b; }
QLabel#dialogTitle { font-size: 14pt; font-weight: 700; color: #1e1b4b; padding-bottom: 6px; }
QLabel#muted { color: #64748b; }
QLabel#error { color: #dc2626; }

QListWidget#nav { background: #1e1b4b; border: none; padding: 12px 8px; outline: 0; }
QListWidget#nav::item { color: #c7d2fe; padding: 11px 14px; margin: 2px 0; border-radius: 10px; }
QListWidget#nav::item:hover { background: #312e81; }
QListWidget#nav::item:selected { background: #4f46e5; color: white; font-weight: 600; }

QPushButton { background: #4f46e5; color: white; border: none; border-radius: 9px;
              padding: 8px 18px; font-weight: 600; }
QPushButton:hover { background: #4338ca; }
QPushButton:pressed { background: #3730a3; }
QPushButton:disabled { background: #cbd5e1; color: #f8fafc; }
QPushButton[variant="secondary"] { background: #e0e7ff; color: #3730a3; }
QPushButton[variant="secondary"]:hover { background: #c7d2fe; }
QPushButton[variant="danger"] { background: #fee2e2; color: #b91c1c; }
QPushButton[variant="danger"]:hover { background: #fecaca; }
QPushButton[variant="success"] { background: #16a34a; }
QPushButton[variant="success"]:hover { background: #15803d; }

QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox, QSpinBox {
    color: #1e293b; background: white; border: 1px solid #cbd5e1; border-radius: 9px; padding: 7px 10px;
    selection-background-color: #c7d2fe; selection-color: #1e1b4b; min-height: 20px; }
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QDoubleSpinBox:focus { border: 2px solid #4f46e5; }
QComboBox::drop-down, QDateEdit::drop-down { border: none; width: 26px; }
QComboBox QAbstractItemView { color: #1e293b; background: white; border: 1px solid #cbd5e1;
                              selection-background-color: #e0e7ff; selection-color: #1e1b4b; }

QTableView, QTableWidget, QListWidget#results { background: white; alternate-background-color: #f8f9ff;
    color: #1e293b; border: 1px solid #e2e8f0; border-radius: 12px; gridline-color: transparent;
    selection-background-color: #e0e7ff; selection-color: #1e1b4b; }
QTableView::item, QTableWidget::item { color: #1e293b; padding: 6px; }
QHeaderView::section { background: #eef2ff; color: #3730a3; padding: 9px; border: none; font-weight: 700; }
QTableCornerButton::section { background: #eef2ff; border: none; }

QTabWidget::pane { border: none; margin-top: 8px; }
QTabBar::tab { background: transparent; color: #64748b; padding: 9px 18px; margin-right: 4px;
               border-radius: 9px; font-weight: 600; }
QTabBar::tab:selected { background: white; color: #4f46e5; }
QTabBar::tab:hover:!selected { background: #e0e7ff; }

QFrame#card { background: white; border: 1px solid #e2e8f0; border-radius: 14px; }
QLabel#cardValue { font-size: 22pt; font-weight: 700; color: #4f46e5; }
QLabel#cardTitle { color: #64748b; font-weight: 600; }

QMenuBar { background: #ffffff; border-bottom: 1px solid #e2e8f0; }
QMenuBar::item { padding: 6px 12px; border-radius: 6px; }
QMenuBar::item:selected { background: #e0e7ff; }
QMenu { background: white; border: 1px solid #e2e8f0; padding: 6px; }
QMenu::item { padding: 7px 24px; border-radius: 6px; }
QMenu::item:selected { background: #e0e7ff; color: #1e1b4b; }
QStatusBar { background: white; color: #64748b; border-top: 1px solid #e2e8f0; }
QMessageBox { background: white; }
QScrollBar:vertical { background: transparent; width: 10px; }
QScrollBar::handle:vertical { background: #cbd5e1; border-radius: 5px; min-height: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
"""


def apply_theme(app) -> None:
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
