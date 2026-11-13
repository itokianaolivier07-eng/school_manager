from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QLabel, QMessageBox, QPushButton,
                             QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from app.ui.utils import handle_error


def _item(text, editable=False):
    it = QTableWidgetItem("" if text is None else str(text))
    if not editable:
        it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
    return it


class GradesView(QWidget):
    """Saisie des notes par classe / matière / trimestre + classement pondéré."""

    def __init__(self, services, ctx):
        super().__init__()
        self.services, self.ctx = services, ctx
        self.class_cb, self.subject_cb, self.term_cb = QComboBox(), QComboBox(), QComboBox()
        for t in (1, 2, 3):
            self.term_cb.addItem(f"Trimestre {t}", t)
        load = QPushButton("Charger")
        load.setObjectName("secondaryButton")
        load.clicked.connect(self.load)
        top = QHBoxLayout()
        top.setSpacing(10)
        for label, w in (("Classe", self.class_cb), ("Matière", self.subject_cb), ("Période", self.term_cb)):
            top.addWidget(QLabel(label))
            top.addWidget(w)
        top.addWidget(load)
        top.addStretch(1)

        self.sheet = QTableWidget(0, 5)
        self.sheet.setHorizontalHeaderLabels(["Matricule", "Nom", "Prénom", "Note /20", "Commentaire"])
        self.sheet.horizontalHeader().setStretchLastSection(True)
        self.can_write = ctx.session.can("grades.write")
        if not self.can_write:
            self.sheet.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.save_btn = QPushButton("Enregistrer les notes")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.setVisible(self.can_write)
        self.save_btn.clicked.connect(self.save)

        self.ranking = QTableWidget(0, 5)
        self.ranking.setHorizontalHeaderLabels(["Rang", "Matricule", "Nom", "Prénom", "Moyenne /20"])
        self.ranking.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ranking.setShowGrid(False)
        self.ranking.setAlternatingRowColors(True)
        self.ranking.horizontalHeader().setStretchLastSection(True)
        self.ranking.verticalHeader().setVisible(False)
        self.ranking.verticalHeader().setDefaultSectionSize(38)
        self.sheet.setShowGrid(False)
        self.sheet.setAlternatingRowColors(True)
        self.sheet.verticalHeader().setVisible(False)
        self.sheet.verticalHeader().setDefaultSectionSize(38)

        tab_sheet = QWidget()
        sheet_layout = QVBoxLayout(tab_sheet)
        sheet_layout.setContentsMargins(10, 10, 10, 10)
        sheet_layout.setSpacing(10)
        sheet_layout.addWidget(self.sheet)
        sheet_layout.addWidget(self.save_btn)
        tabs = QTabWidget()
        tabs.addTab(tab_sheet, "Saisie")
        tabs.addTab(self.ranking, "Classement")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)
        layout.addLayout(top)
        layout.addWidget(tabs, 1)
        self._ids = []

    def refresh(self):
        try:
            for cb, options in ((self.class_cb, self.services.classes.options()),
                                (self.subject_cb, self.services.subjects.options())):
                current = cb.currentData()
                cb.clear()
                for label, val in options:
                    cb.addItem(label, val)
                i = cb.findData(current)
                cb.setCurrentIndex(max(0, i))
        except Exception as e:
            handle_error(self, e)

    def _ctx_values(self):
        c, s, t = self.class_cb.currentData(), self.subject_cb.currentData(), self.term_cb.currentData()
        if c is None or s is None:
            QMessageBox.information(self, "Notes", "Créez d'abord une classe et une matière.")
            return None
        return c, s, t

    def load(self):
        vals = self._ctx_values()
        if not vals:
            return
        c, s, t = vals
        try:
            rows = self.services.grades.sheet(c, s, t)
            ranks = self.services.grades.ranking(c, t)
        except Exception as e:
            return handle_error(self, e)
        self._ids = [r["student_id"] for r in rows]
        self.sheet.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.sheet.setItem(i, 0, _item(r["matricule"]))
            self.sheet.setItem(i, 1, _item(r["last_name"]))
            self.sheet.setItem(i, 2, _item(r["first_name"]))
            self.sheet.setItem(i, 3, _item(r["value"], editable=True))
            self.sheet.setItem(i, 4, _item(r["comment"], editable=True))
        self.ranking.setRowCount(len(ranks))
        for i, r in enumerate(ranks):
            for j, key in enumerate(("rank", "matricule", "last_name", "first_name", "average")):
                self.ranking.setItem(i, j, _item(r[key]))

    def save(self):
        vals = self._ctx_values()
        if not vals:
            return
        c, s, t = vals
        entries = [(sid, self.sheet.item(i, 3).text().strip() or None, self.sheet.item(i, 4).text().strip() or None)
                   for i, sid in enumerate(self._ids)]
        try:
            n = self.services.grades.save_sheet(c, s, t, entries)
        except Exception as e:
            return handle_error(self, e)
        QMessageBox.information(self, "Notes", f"{n} note(s) enregistrée(s).")
        self.load()
