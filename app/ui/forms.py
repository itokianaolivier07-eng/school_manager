from dataclasses import dataclass
from typing import Callable, Optional

from PyQt6.QtCore import QDate
from PyQt6.QtWidgets import (QComboBox, QDateEdit, QDialog, QDialogButtonBox, QDoubleSpinBox,
                             QFormLayout, QLineEdit, QVBoxLayout)


@dataclass
class Field:
    name: str
    label: str
    kind: str = "text"          # text | password | date | combo | number
    required: bool = False
    choices: Optional[Callable] = None   # -> [(libellé, valeur)]
    max_len: int = 100
    minimum: float = 0.0
    maximum: float = 20.0


class FormDialog(QDialog):
    """Formulaire généré à partir d'une liste de Field ; la validation reste dans les services."""

    def __init__(self, title, fields, initial=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(440)
        self.fields = fields
        self.widgets = {}
        initial = initial or {}
        form = QFormLayout()
        for f in fields:
            w = self._make(f, initial.get(f.name))
            self.widgets[f.name] = w
            form.addRow(f.label + (" *" if f.required else ""), w)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _make(self, f, value):
        if f.kind in ("text", "password"):
            w = QLineEdit("" if value is None else str(value))
            w.setMaxLength(128 if f.kind == "password" else f.max_len)
            if f.kind == "password":
                w.setEchoMode(QLineEdit.EchoMode.Password)
                w.setPlaceholderText("Laisser vide pour ne pas changer" if value is not None else "")
                w.setText("")
            return w
        if f.kind == "date":
            w = QDateEdit()
            w.setCalendarPopup(True)
            w.setDisplayFormat("yyyy-MM-dd")
            w.setMinimumDate(QDate(1900, 1, 1))
            d = QDate.fromString(str(value or ""), "yyyy-MM-dd")
            w.setDate(d if d.isValid() else QDate.currentDate())
            return w
        if f.kind == "number":
            w = QDoubleSpinBox()
            w.setDecimals(2)
            w.setRange(f.minimum, f.maximum)
            w.setSingleStep(0.5)
            w.setValue(float(value) if value not in (None, "") else max(f.minimum, 1.0))
            return w
        w = QComboBox()   # combo
        if not f.required:
            w.addItem("— Aucun —", None)
        for label, val in (f.choices() if f.choices else []):
            w.addItem(label, val)
        for i in range(w.count()):
            if w.itemData(i) == value:
                w.setCurrentIndex(i)
                break
        return w

    def values(self):
        out = {}
        for f in self.fields:
            w = self.widgets[f.name]
            if f.kind in ("text", "password"):
                out[f.name] = w.text()
            elif f.kind == "date":
                out[f.name] = w.date().toString("yyyy-MM-dd")
            elif f.kind == "number":
                out[f.name] = w.value()
            else:
                out[f.name] = w.currentData()
        return out
