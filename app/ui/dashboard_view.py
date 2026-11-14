"""Tableau de bord : indicateurs clés, suivi des bénéfices et graphiques."""
from PyQt6.QtCore import QSignalBlocker, Qt
from PyQt6.QtWidgets import (QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea,
                             QVBoxLayout, QWidget)

from app.core import school
from app.ui import theme
from app.ui.charts import ProfitChart, RevenueExpenseChart
from app.ui.utils import handle_error


def _card(title, value, subtitle="", color=None):
    frame = QFrame()
    frame.setObjectName("card")
    value_label = QLabel(str(value))
    value_label.setObjectName("cardValue")
    if color:
        value_label.setStyleSheet(f"color: {color};")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 14, 18, 14)
    layout.setSpacing(3)
    layout.addWidget(value_label)
    title_label = QLabel(title)
    title_label.setObjectName("cardTitle")
    layout.addWidget(title_label)
    if subtitle:
        hint = QLabel(subtitle)
        hint.setObjectName("cardHint")
        layout.addWidget(hint)
    return frame


def _chart_card(title, chart):
    frame = QFrame()
    frame.setObjectName("card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(10)
    label = QLabel(title)
    label.setObjectName("chartTitle")
    layout.addWidget(label)
    layout.addWidget(chart, 1)
    return frame


class MonthDetail(QFrame):
    """Détail chiffré du bénéfice pour le mois sélectionné."""

    def __init__(self, on_month_change):
        super().__init__()
        self.setObjectName("card")
        self.on_month_change = on_month_change
        header = QHBoxLayout()
        title = QLabel("Bénéfice mensuel")
        title.setObjectName("cardTitle")
        self.combo = QComboBox()
        self.combo.setObjectName("dashboardMonthSelect")
        self.combo.currentIndexChanged.connect(self._changed)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(QLabel("Mois"))
        header.addWidget(self.combo)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(28)
        self.grid.setVerticalSpacing(9)
        self.grid.setColumnStretch(1, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 16)
        layout.setSpacing(10)
        layout.addLayout(header)
        layout.addLayout(self.grid)

    def _changed(self, index):
        if index >= 0:
            self.on_month_change(index)

    def set_months(self, months, selected):
        blocker = QSignalBlocker(self.combo)
        self.combo.clear()
        for month in months:
            self.combo.addItem(f"{month['label']} {month['year']}")
        if months:
            self.combo.setCurrentIndex(min(max(selected, 0), len(months) - 1))
        del blocker

    def render(self, month):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        if month is None:
            empty = QLabel("Aucune donnée pour cette année.")
            empty.setObjectName("muted")
            self.grid.addWidget(empty, 0, 0, 1, 2)
            return
        pal = theme.current_palette()
        rows = (
            ("Encaissements du mois", month["collected"], pal["positive"]),
            ("Salaires & avances", -month["salaries"], pal["negative"]),
            ("Loyer", -month["loyer"], pal["negative"]),
            ("Eau / Électricité", -month["utilities"], pal["negative"]),
            ("Autres charges", -month["other"], pal["negative"]),
        )
        for index, (label, value, color) in enumerate(rows):
            self.grid.addWidget(self._text(label, "detailLabel"), index, 0)
            self.grid.addWidget(self._value(school.fmt_ar(value), color, "detailValue"), index, 1)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("detailSeparator")
        self.grid.addWidget(line, len(rows), 0, 1, 2)
        profit = month["profit"]
        profit_text = ("+ " if profit > 0 else "") + school.fmt_ar(profit)
        self.grid.addWidget(self._text("Bénéfice du mois", "detailTotal"), len(rows) + 1, 0)
        self.grid.addWidget(self._value(profit_text, pal["positive"] if profit >= 0 else pal["negative"],
                                        "detailTotal"), len(rows) + 1, 1)

    @staticmethod
    def _text(text, object_name):
        label = QLabel(text)
        label.setObjectName(object_name)
        return label

    @staticmethod
    def _value(text, color, object_name):
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label.setStyleSheet(f"color: {color};")
        return label


class DashboardView(QWidget):
    def __init__(self, services, ctx):
        super().__init__()
        self.services = services
        self.ctx = ctx
        self.finance = None
        self.selected_index = 0

        self.kpi = QGridLayout()
        self.kpi.setSpacing(16)

        self.year_cb = QComboBox()
        self.year_cb.setObjectName("dashboardSchoolYearFilter")
        self.year_cb.currentIndexChanged.connect(self._year_changed)
        self.fin_kpi = QGridLayout()
        self.fin_kpi.setSpacing(16)
        self.revenue_chart = RevenueExpenseChart()
        self.profit_chart = ProfitChart()
        self.detail = MonthDetail(self._month_selected)
        self.finance_box = self._build_finance_box()

        content = QWidget()
        content.setObjectName("page")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(16)
        layout.addLayout(self.kpi)
        layout.addWidget(self.finance_box)
        layout.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        scroll.viewport().setAutoFillBackground(False)
        scroll.setWidget(content)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    # --- construction ---
    def _build_finance_box(self):
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        header = QHBoxLayout()
        title = QLabel("Suivi des bénéfices")
        title.setObjectName("sectionTitle")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(QLabel("Année scolaire"))
        header.addWidget(self.year_cb)

        charts = QHBoxLayout()
        charts.setSpacing(16)
        charts.addWidget(_chart_card("Recettes et dépenses par mois", self.revenue_chart), 3)
        charts.addWidget(_chart_card("Bénéfice net par mois", self.profit_chart), 2)

        layout.addLayout(header)
        layout.addLayout(self.fin_kpi)
        layout.addLayout(charts)
        layout.addWidget(self.detail)
        return box

    # --- rafraîchissement ---
    def refresh(self):
        try:
            data = self.services.dashboard.summary()
        except Exception as e:
            return handle_error(self, e)
        self._render_kpis(data)
        available = self.services.dashboard.finance_available()
        self.finance_box.setVisible(available)
        if not available:
            self.finance = None
            return
        try:
            self._sync_year(self.services.dashboard.finance_year_options())
        except Exception as e:
            return handle_error(self, e)
        self._load_finance(reset=True)

    def _load_finance(self, reset=False):
        try:
            self.finance = self.services.dashboard.finance_series(self.year_cb.currentData())
        except Exception as e:
            return handle_error(self, e)
        if reset and self.finance:
            self.selected_index = self.finance["default_index"]
        self._render_finance()

    def _render_kpis(self, data):
        self._clear(self.kpi)
        cards = [("Élèves actifs", data["students"]),
                 ("Classes", data["classes"]),
                 ("Employés", data["employees"])]
        if "present_today" in data:
            cards.append(("Présents aujourd'hui", data["present_today"]))
        if "salary_total" in data:
            cards.append(("Masse salariale / mois", school.fmt_ar(data["salary_total"])))
        for index, (title, value) in enumerate(cards):
            self.kpi.addWidget(_card(title, value), 0, index)

    def _render_finance(self):
        self._clear(self.fin_kpi)
        finance = self.finance
        if not finance or not finance["months"]:
            self.revenue_chart.set_data([], [])
            self.revenue_chart.set_selected(-1)
            self.profit_chart.set_data([], [])
            self.profit_chart.set_selected(-1)
            self.detail.set_months([], 0)
            self.detail.render(None)
            return
        months = finance["months"]
        self.selected_index = min(max(self.selected_index, 0), len(months) - 1)
        month = months[self.selected_index]
        self._render_finance_kpis(month, finance["totals"], finance["school_year"])
        labels = [item["short_label"] for item in months]
        pal = theme.current_palette()
        self.revenue_chart.set_data(labels, [
            ("Recettes", pal["series_1"], [item["collected"] for item in months]),
            ("Dépenses", pal["series_2"], [item["spending"] for item in months]),
        ])
        self.profit_chart.set_data(labels, [item["profit"] for item in months])
        self.detail.set_months(months, self.selected_index)
        self._select_month(self.selected_index, render_detail=True)

    def _render_finance_kpis(self, month, totals, school_year):
        pal = theme.current_palette()
        cards = [
            ("Bénéfice du mois", ("+ " if month["profit"] > 0 else "") + school.fmt_ar(month["profit"]),
             f"{month['label']} {month['year']}", pal["positive"] if month["profit"] >= 0 else pal["negative"]),
            ("Bénéfice cumulé", ("+ " if totals["profit"] > 0 else "") + school.fmt_ar(totals["profit"]),
             f"Année {school_year}", pal["positive"] if totals["profit"] >= 0 else pal["negative"]),
            ("Encaissements du mois", school.fmt_ar(month["collected"]),
             "Écolage et inscriptions", pal["series_1"]),
            ("Dépenses du mois", school.fmt_ar(month["spending"]),
             "Salaires et charges", pal["warning"]),
        ]
        for index, (title, value, subtitle, color) in enumerate(cards):
            self.fin_kpi.addWidget(_card(title, value, subtitle, color), 0, index)

    # --- interactions ---
    def _sync_year(self, years):
        values = list(years)
        current = self.year_cb.currentData()
        if values and [self.year_cb.itemData(i) for i in range(self.year_cb.count())] == values:
            return
        blocker = QSignalBlocker(self.year_cb)
        self.year_cb.clear()
        for year in values:
            self.year_cb.addItem(f"Année scolaire {year}", year)
        index = self.year_cb.findData(current)
        self.year_cb.setCurrentIndex(index if index >= 0 else 0)
        del blocker

    def _year_changed(self, _index):
        if self.year_cb.currentData() is not None:
            self._load_finance(reset=True)

    def _month_selected(self, index):
        if self.finance:
            self._select_month(index, render_detail=True)

    def _select_month(self, index, render_detail=False):
        self.selected_index = index
        self.revenue_chart.set_selected(index)
        self.profit_chart.set_selected(index)
        if render_detail and self.finance:
            self.detail.render(self.finance["months"][index])

    @staticmethod
    def _clear(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
