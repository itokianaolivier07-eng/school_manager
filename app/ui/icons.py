"""Icônes du menu latéral dessinées au QPainter (pas de dépendance externe)."""
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


def _canvas(size=22):
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    return pix, painter


def _stroke(painter, color, width=1.8):
    painter.setPen(QPen(QColor(color), width, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.setBrush(Qt.BrushStyle.NoBrush)


def _to_icon(pix, painter):
    painter.end()
    return QIcon(pix)


def icon_dashboard(color="#1e293b"):
    pix, p = _canvas()
    _stroke(p, color)
    for x in (4.5, 12.5):
        for y in (4.5, 12.5):
            p.drawRoundedRect(QRectF(x, y, 5.5, 5.5), 1.5, 1.5)
    return _to_icon(pix, p)


def icon_students(color="#1e293b"):
    pix, p = _canvas()
    _stroke(p, color)
    p.drawEllipse(QPointF(11, 7.5), 4, 4)
    path = QPainterPath()
    path.moveTo(4, 20)
    path.cubicTo(4, 14, 18, 14, 18, 20)
    p.drawPath(path)
    return _to_icon(pix, p)


def icon_employees(color="#1e293b"):
    pix, p = _canvas()
    _stroke(p, color)
    p.drawEllipse(QPointF(9, 8), 3.2, 3.2)
    p.drawEllipse(QPointF(15, 10), 2.4, 2.4)
    p1 = QPainterPath()
    p1.moveTo(3, 19)
    p1.cubicTo(3, 13, 15, 13, 15, 19)
    p.drawPath(p1)
    p2 = QPainterPath()
    p2.moveTo(12, 19)
    p2.cubicTo(12, 15.5, 19, 15.5, 19, 19)
    p.drawPath(p2)
    return _to_icon(pix, p)


def icon_classes(color="#1e293b"):
    pix, p = _canvas()
    _stroke(p, color)
    p.drawLine(QPointF(11, 4.5), QPointF(11, 9))
    p.drawEllipse(QPointF(11, 11), 5.5, 3)
    p.drawLine(QPointF(5.5, 11), QPointF(5.5, 14.5))
    p.drawLine(QPointF(16.5, 11), QPointF(16.5, 14.5))
    p.drawLine(QPointF(11, 14), QPointF(11, 18.5))
    p.drawLine(QPointF(7, 15.5), QPointF(15, 15.5))
    return _to_icon(pix, p)


def icon_attendance(color="#1e293b"):
    pix, p = _canvas()
    _stroke(p, color)
    p.drawEllipse(QPointF(11, 11.5), 7, 7)
    p.drawLine(QPointF(11, 11.5), QPointF(11, 7))
    p.drawLine(QPointF(11, 11.5), QPointF(15, 13.5))
    return _to_icon(pix, p)


def icon_salaries(color="#1e293b"):
    pix, p = _canvas()
    _stroke(p, color)
    p.drawRoundedRect(QRectF(3.5, 5.5, 15, 11), 2.5, 2.5)
    p.drawLine(QPointF(3.5, 11), QPointF(18.5, 11))
    p.drawEllipse(QPointF(11, 11), 2.2, 2.2)
    p.drawLine(QPointF(8.5, 11), QPointF(8.5, 11))
    return _to_icon(pix, p)


def icon_fees(color="#1e293b"):
    pix, p = _canvas()
    _stroke(p, color)
    p.drawRoundedRect(QRectF(5, 3.5, 12, 15), 2, 2)
    for y in (8, 11, 14):
        p.drawLine(QPointF(8, y), QPointF(14, y))
    p.drawEllipse(QPointF(15, 4.5), 1.2, 1.2)
    return _to_icon(pix, p)


def icon_expenses(color="#1e293b"):
    pix, p = _canvas()
    _stroke(p, color)
    p.drawRoundedRect(QRectF(4, 6, 14, 10), 2.5, 2.5)
    p.drawLine(QPointF(7, 11), QPointF(11, 11))
    p.drawLine(QPointF(15, 11), QPointF(15, 11))
    p.drawEllipse(QPointF(13, 11), 1.3, 1.3)
    return _to_icon(pix, p)


def icon_users(color="#1e293b"):
    pix, p = _canvas()
    _stroke(p, color)
    p.drawEllipse(QPointF(11, 8), 4, 4)
    path = QPainterPath()
    path.moveTo(4, 19.5)
    path.cubicTo(4, 14, 18, 14, 18, 19.5)
    p.drawPath(path)
    p.drawLine(QPointF(11, 2.5), QPointF(11, 5.5))
    return _to_icon(pix, p)


def icon_logout(color="#1e293b"):
    pix, p = _canvas()
    _stroke(p, color)
    p.drawRoundedRect(QRectF(3, 5, 8, 12), 1.5, 1.5)
    p.drawLine(QPointF(11, 11), QPointF(18, 11))
    p.drawLine(QPointF(15, 8), QPointF(18, 11))
    p.drawLine(QPointF(15, 14), QPointF(18, 11))
    return _to_icon(pix, p)


def icon_logo():
    """Logo de l'application - équerre dans un hexagone arrondi."""
    pix, p = _canvas(36)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor("#4f46e5"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(3, 3, 30, 30), 10, 10)
    p.setPen(QPen(QColor("white"), 2.6, Qt.PenStyle.SolidLine,
                  Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawLine(QPointF(10, 24), QPointF(18, 12))
    p.drawLine(QPointF(18, 12), QPointF(26, 24))
    p.drawLine(QPointF(13, 19.5), QPointF(23, 19.5))
    p.drawEllipse(QPointF(18, 10), 1.6, 1.6)
    return _to_icon(pix, p)


NAV_ICONS = {
    "Tableau de bord": icon_dashboard,
    "Élèves": icon_students,
    "Employés": icon_employees,
    "Classes": icon_classes,
    "Pointage": icon_attendance,
    "Salaires": icon_salaries,
    "Écolages": icon_fees,
    "Charges": icon_expenses,
    "Utilisateurs": icon_users,
}
