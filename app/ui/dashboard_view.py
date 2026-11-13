from PyQt6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from app.core import school
from app.ui.utils import handle_error


def _card(title, value):
    frame = QFrame()
    frame.setObjectName("card")
    v = QLabel(str(value))
    v.setObjectName("cardValue")
    t = QLabel(title)
    t.setObjectName("cardTitle")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(20, 16, 20, 16)
    lay.addWidget(v)
    lay.addWidget(t)
    return frame


class DashboardView(QWidget):
    def __init__(self, services, ctx):
        super().__init__()
        self.services = services
        self.grid = QGridLayout(self)
        self.grid.setSpacing(16)

    def refresh(self):
        try:
            d = self.services.dashboard.summary()
        except Exception as e:
            return handle_error(self, e)
        while self.grid.count():
            self.grid.takeAt(0).widget().deleteLater()
        cards = [("Élèves actifs", d["students"]), ("Classes", d["classes"]), ("Enseignants", d["teachers"])]
        if "collected_year" in d:
            cards += [(f"Encaissé ({d['school_year']})", school.fmt_ar(d["collected_year"])),
                      ("Encaissé ce mois", school.fmt_ar(d["collected_month"]))]
        for i, (title, value) in enumerate(cards):
            self.grid.addWidget(_card(title, value), i // 3, i % 3)
        self.grid.setRowStretch(len(cards) // 3 + 1, 1)
