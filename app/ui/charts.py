"""Graphiques financiers légers dessinés au QPainter (sans dépendance externe)."""
import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

from app.ui import theme


def _chart_colors() -> dict:
    p = theme.current_palette()
    return {
        "grid": QColor(p["border"]),
        "zero": QColor(p["input_border"]),
        "text": QColor(p["muted"]),
        "highlight": QColor(p["active"]),
        "empty": QColor(p["faint"]),
    }


def _fmt_short(value) -> str:
    number = float(value)
    magnitude = abs(number)
    if magnitude >= 1_000_000:
        return f"{number / 1_000_000:.1f}".rstrip("0").rstrip(".") + " M"
    if magnitude >= 1_000:
        return f"{round(number / 1_000)} k"
    return str(int(number))


def _nice_ceiling(value) -> float:
    if value <= 0:
        return 1.0
    base = 10.0 ** math.floor(math.log10(value))
    for step in (1, 1.5, 2, 2.5, 3, 4, 5, 7.5, 10):
        if value <= step * base:
            return step * base
    return 10 * base


class _BaseChart(QWidget):
    pad_left, pad_right, pad_top, pad_bottom = 68, 16, 26, 30
    grid_lines = 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self.labels = []
        self.selected = -1
        self.setMinimumHeight(240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_selected(self, index):
        self.selected = index
        self.update()

    def plot_rect(self) -> QRectF:
        return QRectF(self.pad_left, self.pad_top,
                      max(1.0, self.width() - self.pad_left - self.pad_right),
                      max(1.0, self.height() - self.pad_top - self.pad_bottom))

    def _small_font(self) -> QFont:
        font = QFont(self.font())
        font.setPointSizeF(8.0)
        return font

    def draw_highlight(self, painter, rect, count):
        if self.selected < 0 or self.selected >= count or count <= 0:
            return
        slot = rect.width() / count
        painter.fillRect(
            QRectF(rect.left() + slot * self.selected, rect.top(), slot, rect.height()),
            _chart_colors()["highlight"])

    def draw_labels(self, painter, rect):
        count = len(self.labels)
        if not count:
            return
        slot = rect.width() / count
        painter.setFont(self._small_font())
        text = _chart_colors()["text"]
        for index, label in enumerate(self.labels):
            painter.setPen(text)
            painter.drawText(QRectF(rect.left() + slot * index, rect.bottom() + 6, slot, 18),
                             Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, label)

    def draw_empty(self, painter, rect):
        painter.setFont(self._small_font())
        painter.setPen(_chart_colors()["empty"])
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Aucune donnée pour cette année.")


class RevenueExpenseChart(_BaseChart):
    """Barres groupées : recettes et dépenses de chaque mois."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.series = []  # (nom, QColor, valeurs)

    def set_data(self, labels, series):
        self.labels = list(labels)
        self.series = [(name, QColor(color), list(values)) for name, color, values in series]
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.plot_rect()
        count = len(self.labels)
        peak = max([0] + [max(values, default=0) for _, _, values in self.series])
        top = _nice_ceiling(peak)
        self.draw_highlight(painter, rect, count)
        self.draw_axis(painter, rect, top)
        if not count:
            self.draw_empty(painter, rect)
            return
        slot = rect.width() / count
        group = min(slot * 0.68, 84)
        bar = group / max(1, len(self.series))
        for index in range(count):
            start_x = rect.left() + slot * index + (slot - group) / 2
            for position, (_, color, values) in enumerate(self.series):
                value = values[index] if index < len(values) else 0
                height = rect.height() * (value / top) if top else 0
                painter.fillRect(
                    QRectF(start_x + bar * position, rect.bottom() - height,
                           max(1.0, bar - 3), height), color)
        self.draw_labels(painter, rect)
        self.draw_legend(painter, rect)

    def draw_axis(self, painter, rect, top):
        painter.setFont(self._small_font())
        colors = _chart_colors()
        for line in range(self.grid_lines + 1):
            y = rect.top() + rect.height() * line / self.grid_lines
            painter.setPen(QPen(colors["grid"], 1))
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            painter.setPen(colors["text"])
            painter.drawText(QRectF(0, y - 9, self.pad_left - 8, 18),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             _fmt_short(top * (self.grid_lines - line) / self.grid_lines))

    def draw_legend(self, painter, rect):
        painter.setFont(self._small_font())
        x, y = rect.left(), 4
        text = _chart_colors()["text"]
        for name, color, _ in self.series:
            painter.fillRect(QRectF(x, y + 4, 11, 11), color)
            painter.setPen(text)
            painter.drawText(QRectF(x + 16, y, 120, 18),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)
            x += 26 + painter.fontMetrics().horizontalAdvance(name)


class ProfitChart(_BaseChart):
    """Barres divergentes : bénéfice net (positif/négatif) de chaque mois."""

    POSITIVE = QColor("#10b981")
    NEGATIVE = QColor("#ef4444")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.values = []

    def set_data(self, labels, values):
        self.labels = list(labels)
        self.values = list(values)
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.plot_rect()
        count = len(self.labels)
        peak = max([abs(value) for value in self.values], default=0)
        top = _nice_ceiling(peak)
        self.draw_highlight(painter, rect, count)
        self.draw_axis(painter, rect, top)
        if not count:
            self.draw_empty(painter, rect)
            return
        baseline = rect.center().y()
        slot = rect.width() / count
        bar = min(slot * 0.5, 48)
        for index, value in enumerate(self.values):
            height = abs(value) / top * (rect.height() / 2)
            x = rect.left() + slot * index + (slot - bar) / 2
            top_y = baseline - height if value >= 0 else baseline
            painter.fillRect(QRectF(x, top_y, bar, height),
                             self.POSITIVE if value >= 0 else self.NEGATIVE)
        self.draw_labels(painter, rect)

    def draw_axis(self, painter, rect, top):
        painter.setFont(self._small_font())
        colors = _chart_colors()
        for line in range(self.grid_lines + 1):
            fraction = line / self.grid_lines
            y = rect.top() + rect.height() * fraction
            value = top * (1 - 2 * fraction)
            is_zero = abs(value) < 1e-9
            painter.setPen(QPen(colors["zero"] if is_zero else colors["grid"],
                                1.6 if is_zero else 1))
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            painter.setPen(colors["text"])
            painter.drawText(QRectF(0, y - 9, self.pad_left - 8, 18),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             _fmt_short(value))
