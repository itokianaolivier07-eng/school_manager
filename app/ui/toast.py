from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QLabel

_COLORS = {"success": "#16a34a", "info": "#4f46e5", "error": "#dc2626"}


def show_toast(widget, text, kind="success", ms=2800):
    """Petite notification non bloquante en bas à droite de la fenêtre."""
    win = widget.window()
    color = _COLORS[kind]
    label = QLabel(text, win)
    label.setStyleSheet(f"background: {color}; color: white; padding: 12px 22px; "
                        "border-radius: 12px; font-weight: 600;")
    label.adjustSize()
    label.move(max(10, win.width() - label.width() - 28), max(10, win.height() - label.height() - 52))
    label.show()
    label.raise_()
    QTimer.singleShot(ms, label.deleteLater)
