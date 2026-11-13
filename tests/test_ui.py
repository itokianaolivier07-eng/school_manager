import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QComboBox, QDoubleSpinBox, QLineEdit, QTableWidget

from app.ui.forms import Field, FormDialog
from app.ui.dialogs import LoginDialog
from app.ui.main_window import MainWindow
from app.ui.theme import apply_theme
from app.ui.views import classes_view
from tests.conftest import make_env


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    apply_theme(app)
    return app


def test_main_window_builds_all_authorized_pages(qapp):
    ctx, services = make_env()
    window = MainWindow(services, ctx)

    assert window.stack.count() == 9
    labels = [window.nav.item(i).text() for i in range(window.nav.count())]
    assert labels[0] == "Tableau de bord"
    assert all(not any(ord(char) > 0xFFFF for char in label) for label in labels)
    window.close()


def test_number_field_uses_configured_precision(qapp):
    dialog = FormDialog("Montant", [Field("amount", "Montant", "number", decimals=0, step=1000)])
    amount = dialog.widgets["amount"]

    assert isinstance(amount, QDoubleSpinBox)
    assert amount.decimals() == 0
    assert amount.singleStep() == 1000
    dialog.close()


def test_login_focuses_identifier_for_keyboard_input(qapp):
    dialog = LoginDialog(None)
    dialog.show()
    qapp.processEvents()

    assert dialog.user.hasFocus()
    QTest.keyClicks(dialog.user, "admin")
    assert dialog.user.text() == "admin"
    dialog.close()


def test_input_and_table_text_are_dark(qapp):
    line = QLineEdit()
    combo = QComboBox()
    table = QTableWidget(1, 1)
    for widget in (line, combo, table):
        widget.ensurePolished()

    assert line.palette().color(line.foregroundRole()).name() == "#1e293b"
    assert combo.palette().color(combo.foregroundRole()).name() == "#1e293b"
    assert table.palette().color(table.foregroundRole()).name() == "#1e293b"


def test_class_screen_uses_employee_and_has_no_level(qapp):
    ctx, services = make_env()
    employee_id = services.teachers.create({
        "employee_no": "EMP001",
        "first_name": "Aina",
        "last_name": "Rakoto",
        "gender": "F",
        "birth_date": "1985-04-12",
        "hire_date": "2020-09-01",
    })
    view = classes_view(services, ctx)

    assert all(column[1] != "Niveau" for column in view.columns)
    assert all(field.name != "level" for field in view.fields)
    employee = next(field for field in view.fields if field.name == "main_teacher_id")
    assert employee.label == "Employé"
    assert employee.choices() == [("EMP001 — Rakoto Aina", employee_id)]
