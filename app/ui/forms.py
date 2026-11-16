from dataclasses import dataclass
from typing import Callable, Optional

from PyQt6.QtCore import QDate, QTime, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QApplication, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QDoubleSpinBox,
                             QCheckBox, QFormLayout, QFrame, QGridLayout, QLabel, QLineEdit, QScrollArea,
                             QTimeEdit, QVBoxLayout, QWidget, QHBoxLayout)


@dataclass
class Field:
    name: str
    label: str
    kind: str = "text"
    required: bool = False
    choices: Optional[Callable] = None
    max_len: int = 100
    minimum: float = 0.0
    maximum: float = 20.0
    decimals: int = 2
    step: float = 0.5
    default: Optional[float] = None
    placeholder: str = ""


class FormDialog(QDialog):
    def __init__(self, title, fields, initial=None, parent=None, readonly=False, columns=1):
        super().__init__(parent)
        self.setObjectName("appDialog")
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(640 if columns > 1 else 460)
        self.fields = fields
        self.widgets = {}
        self.time_enabled = {}
        self.readonly = readonly
        initial = initial or {}
        form = self.form = QGridLayout() if columns > 1 else QFormLayout()
        if columns > 1:
            form.setHorizontalSpacing(16)
            form.setVerticalSpacing(8)
        for index, f in enumerate(fields):
            w = self._make(f, initial.get(f.name))
            if readonly:
                w.setEnabled(False)
            self.widgets[f.name] = w
            field_widget = w
            if f.kind == "time":
                enabled = QCheckBox("Renseigner")
                enabled.setChecked(bool(initial.get(f.name)))
                enabled.setEnabled(not readonly)
                enabled.toggled.connect(w.setEnabled)
                w.setEnabled(enabled.isChecked() and not readonly)
                self.time_enabled[f.name] = enabled
                field_layout = QHBoxLayout()
                field_layout.setContentsMargins(0, 0, 0, 0)
                field_layout.addWidget(enabled)
                field_layout.addWidget(w, 1)
                field_widget = QWidget()
                field_widget.setLayout(field_layout)
            label = f.label + (" *" if f.required and not readonly else "")
            if columns > 1:
                column_layout = QVBoxLayout()
                column_layout.setContentsMargins(0, 0, 0, 0)
                column_layout.setSpacing(3)
                field_label = QLabel(label)
                field_label.setBuddy(w)
                column_layout.addWidget(field_label)
                column_layout.addWidget(field_widget)
                column_widget = QWidget()
                column_widget.setLayout(column_layout)
                form.addWidget(column_widget, index // columns, index % columns)
            else:
                form.addRow(label, field_widget)
        if readonly:
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
            buttons.rejected.connect(self.reject)
            buttons.accepted.connect(self.accept)
        else:
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Enregistrer")
            buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuler")
            buttons.accepted.connect(self.accept)
            buttons.rejected.connect(self.reject)
        for button in buttons.buttons():
            button.setIcon(QIcon())
        # Les champs défilent si l'écran est petit ; les boutons restent toujours visibles.
        content = QWidget()
        content.setObjectName("formContent")
        content.setLayout(form)
        scroll = QScrollArea()
        scroll.setObjectName("formScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        layout = QVBoxLayout(self)
        layout.addWidget(scroll)
        layout.addWidget(buttons)
        screen = QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            self.setMaximumHeight(int(avail.height() * 0.92))
            self.resize(self.width(), min(content.sizeHint().height() + 90, int(avail.height() * 0.92)))

    def _make(self, f, value):
        if f.kind in ("text", "password"):
            w = QLineEdit("" if value is None else str(value))
            w.setMaxLength(128 if f.kind == "password" else f.max_len)
            w.setPlaceholderText(f.placeholder)
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
        if f.kind == "time":
            w = QTimeEdit()
            w.setDisplayFormat("HH:mm")
            t = QTime.fromString(str(value or ""), "HH:mm")
            w.setTime(t if t.isValid() else QTime(8, 0))
            return w
        if f.kind == "number":
            w = QDoubleSpinBox()
            w.setDecimals(f.decimals)
            w.setRange(f.minimum, f.maximum)
            w.setSingleStep(f.step)
            default = f.default if f.default is not None else max(f.minimum, 1.0)
            w.setValue(float(value) if value not in (None, "") else default)
            return w
        w = QComboBox()
        if not f.required:
            w.addItem("- Aucun -", None)
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
            elif f.kind == "time":
                out[f.name] = w.time().toString("HH:mm") if self.time_enabled[f.name].isChecked() else None
            elif f.kind == "number":
                out[f.name] = w.value()
            else:
                out[f.name] = w.currentData()
        return out
