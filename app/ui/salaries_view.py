"""Consultation des rémunérations de base et historique des sorties."""
from PyQt6.QtCore import QDate
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QComboBox, QDateEdit, QDialog, QDialogButtonBox, QDoubleSpinBox,
                             QFormLayout, QLabel, QVBoxLayout, QWidget, QTabWidget)

from app.core.exceptions import AppError
from app.ui.crud_view import CrudView
from app.ui.forms import Field, FormDialog
from app.ui.utils import handle_error

PAY_TYPES = (("Mensuelle", "monthly"), ("Horaire", "hourly"))


class SalaryBaseDialog(FormDialog):
    def __init__(self, title, fields, initial, parent, *, readonly=False, salaries):
        self.salaries = salaries
        super().__init__(title, fields, initial, parent, readonly=readonly)
        self.widgets["employee_id"].currentIndexChanged.connect(self._employee_changed)
        self._employee_changed()

    def _employee_changed(self):
        employee_id = self.widgets["employee_id"].currentData()
        if employee_id is None:
            return
        pay_type = self.salaries.recommended_pay_type(employee_id)
        is_hourly = pay_type == "hourly"
        for field in ("monthly_amount", "hourly_rate"):
            widget = self.widgets[field]
            visible = (field == "hourly_rate") == is_hourly
            widget.setVisible(visible)
            self.layout().itemAt(0).layout().labelForField(widget).setVisible(visible)


class SalaryDisbursementDialog(QDialog):
    def __init__(self, salaries, disbursements, parent=None):
        super().__init__(parent)
        self.salaries, self.disbursements = salaries, disbursements
        self.setWindowTitle("Nouvelle sortie de salaire")
        self.setModal(True)
        self.setMinimumWidth(440)
        self.error = QLabel()
        self.error.setStyleSheet("color: #b00020;")
        self.error.setWordWrap(True)

        self.employee = QComboBox()
        self.compensations = {}
        for item in salaries.compensation_options():
            label = f"{item['employee_no']} — {item['last_name']} {item['first_name']}"
            if item["position"]:
                label += f" ({item['position']})"
            self.employee.addItem(label, item["employee_id"])
            self.compensations[item["employee_id"]] = item

        self.title = QComboBox()
        for title in disbursements.TITLES:
            self.title.addItem(title, title)
        self.payout_date = QDateEdit(QDate.currentDate())
        self.payout_date.setCalendarPopup(True)
        self.payout_date.setDisplayFormat("yyyy-MM-dd")
        self.hours = QDoubleSpinBox()
        self.hours.setRange(0.01, 1000)
        self.hours.setDecimals(2)
        self.hours.setSingleStep(1)
        self.amount = QDoubleSpinBox()
        self.amount.setRange(1, 50_000_000)
        self.amount.setDecimals(0)
        self.amount.setSingleStep(1000)
        self.rate = QLabel()
        self.preview = QLabel()
        self.hours_label = QLabel("Heures travaillées")
        self.rate_label = QLabel("Indemnité horaire")
        self.amount_label = QLabel("Montant (Ar)")

        form = QFormLayout()
        form.addRow("Employé", self.employee)
        form.addRow("Titre de sortie", self.title)
        form.addRow("Date de sortie", self.payout_date)
        form.addRow(self.hours_label, self.hours)
        form.addRow(self.rate_label, self.rate)
        form.addRow(self.amount_label, self.amount)
        form.addRow("", self.preview)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Enregistrer")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuler")
        for button in buttons.buttons():
            button.setIcon(QIcon())
        buttons.accepted.connect(self._submit)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.error)
        layout.addWidget(buttons)
        self.employee.currentIndexChanged.connect(self._update_compensation)
        self.hours.valueChanged.connect(self._update_preview)
        self._update_compensation()

    def _update_compensation(self):
        compensation = self.compensations.get(self.employee.currentData())
        is_hourly = compensation is not None and compensation["pay_type"] == "hourly"
        self.hours_label.setVisible(is_hourly)
        self.hours.setVisible(is_hourly)
        self.rate_label.setVisible(is_hourly)
        self.rate.setVisible(is_hourly)
        self.preview.setVisible(is_hourly)
        self.amount_label.setVisible(not is_hourly)
        self.amount.setVisible(not is_hourly)
        if is_hourly:
            self.rate.setText(f"{compensation['hourly_rate']:,} Ar / heure".replace(",", " "))
            self._update_preview()

    def _update_preview(self):
        compensation = self.compensations.get(self.employee.currentData())
        if compensation and compensation["pay_type"] == "hourly":
            amount = round(self.hours.value() * compensation["hourly_rate"])
            self.preview.setText(f"Montant calculé : {amount:,} Ar".replace(",", " "))

    def _submit(self):
        employee_id = self.employee.currentData()
        compensation = self.compensations.get(employee_id)
        data = {
            "employee_id": employee_id,
            "title": self.title.currentData(),
            "payout_date": self.payout_date.date().toString("yyyy-MM-dd"),
        }
        if compensation and compensation["pay_type"] == "hourly":
            data["hours"] = self.hours.value()
        else:
            data["amount"] = self.amount.value()
        try:
            self.disbursements.record(data)
        except AppError as exc:
            self.error.setText(str(exc))
            return
        except Exception as exc:
            handle_error(self, exc)
            return
        self.accept()


class SalariesView(QWidget):
    def __init__(self, services, ctx):
        super().__init__()
        self.services = services
        self.tabs = QTabWidget()
        columns = [
            ("employee_no", "N° employé"), ("employee_label", "Employé"),
            ("position", "Poste"), ("pay_type", "Type", dict((v, k) for k, v in PAY_TYPES)),
            ("base_amount", "Rémunération de base (Ar)"), ("updated_at", "Mis à jour"),
        ]
        fields = [
            Field("employee_id", "Employé", "combo", required=True, choices=services.teachers.options),
            Field("monthly_amount", "Salaire mensuel (Ar)", "number", minimum=1,
                  maximum=50_000_000, decimals=0, step=1000, default=1),
            Field("hourly_rate", "Indemnité horaire (Ar)", "number", minimum=1,
                  maximum=50_000_000, decimals=0, step=500, default=1),
        ]
        self.base_view = CrudView(
            services.salaries, columns, fields, ctx, noun="rémunération",
            dialog_factory=lambda title, dialog_fields, initial, parent, readonly=False:
                SalaryBaseDialog(title, dialog_fields, initial, parent, readonly=readonly,
                                 salaries=services.salaries))
        self.tabs.addTab(self.base_view, "Rémunérations de base")

        payout_columns = [
            ("employee_no", "N° employé"), ("employee_name", "Employé"),
            ("position", "Profession"), ("title", "Titre de sortie"),
            ("payout_date", "Date de sortie"), ("school_year", "Année scolaire"),
            ("hours", "Heures"), ("hourly_rate", "Tarif horaire (Ar)"),
            ("amount", "Montant (Ar)"),
        ]
        actions = [("Nouvelle sortie", self._new_disbursement, "salaries.write")]
        self.history_view = CrudView(
            services.salary_disbursements, payout_columns, [], ctx, noun="sortie de salaire",
            read_only=True, extra_actions=actions, show_row_actions=False)
        self.tabs.addTab(self.history_view, "Historique des sorties")
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)

    def _new_disbursement(self, view):
        dialog = SalaryDisbursementDialog(
            self.services.salaries, self.services.salary_disbursements, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            view.refresh()

    def refresh(self):
        current = self.tabs.currentWidget()
        if current is self.base_view:
            self.base_view.refresh()
        elif current is self.history_view:
            self.history_view.refresh()
