import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import (QApplication, QComboBox, QDialogButtonBox, QDoubleSpinBox, QLineEdit,
                             QMessageBox, QTableWidget, QToolButton)

from app.core import school
from app.ui.forms import Field, FormDialog
from app.ui.dialogs import LoginDialog
from app.ui.fees_view import FeesView
from app.ui.main_window import MainWindow
from app.ui.table_model import RowsModel
from app.ui.theme import PALETTE, apply_theme
from app.ui.salaries_view import SalaryBaseDialog, SalariesView
from app.ui.utils import ask_confirmation, handle_error
from app.ui.views import classes_view, students_view
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
    labels = [button.label_text for button in window.sidebar._buttons]
    assert labels[0] == "Tableau de bord"
    assert all(not any(ord(char) > 0xFFFF for char in label) for label in labels)
    assert window.user_info.text() == "Admin - Administrateur"
    assert window.user_info.alignment() == Qt.AlignmentFlag.AlignCenter
    assert window.menuWidget() is None
    toolbar_menus = [button for button in window.top_toolbar.findChildren(QToolButton) if button.text()]
    assert [button.text() for button in toolbar_menus] == ["Compte", "Données"]
    assert not window.findChild(QToolButton, "themeToggleBtn")
    assert [action.text() for action in toolbar_menus[0].menu().actions()] == [
        "Changer le mot de passe…", "Se déconnecter"]
    window.close()


def test_dashboard_tracks_monthly_profit_and_charges_page(qapp):
    ctx, services = make_env()
    services.classes.create({"name": "Classe tableau", "school_year": school.current_school_year()})
    start = school.current_school_year()[:4]
    ctx.db.execute("INSERT INTO expenses (category, label, amount, expense_date) "
                   "VALUES ('loyer', 'Loyer', 300000, ?)", (f"{start}-09-05",))

    window = MainWindow(services, ctx)
    dashboard = window.stack.widget(0)

    assert dashboard.finance is not None
    assert dashboard.detail.combo.count() == len(school.SCHOOL_MONTHS) + 2   # + juillet et août
    assert len(dashboard.profit_chart.values) == len(school.SCHOOL_MONTHS) + 2
    assert any(value < 0 for value in dashboard.profit_chart.values)
    labels = [button.label_text for button in window.sidebar._buttons]
    assert labels.index("Charges") == labels.index("Écolages") + 1
    window.close()


def test_mutations_refresh_related_views_and_annual_filters(qapp):
    ctx, services = make_env()
    window = MainWindow(services, ctx)
    class_view = window.stack.widget(3)
    year = "2024-2025"
    class_id = services.classes.create({"name": "Classe ajoutée", "school_year": year})

    class_view.notify_changed()

    classes_filter = window.findChild(QComboBox, "classesSchoolYearFilter")
    students_filter = window.findChild(QComboBox, "studentsSchoolYearFilter")
    assert classes_filter.findText(year) >= 0
    assert students_filter.findText(year) >= 0
    assert class_view.model.rowCount() == 1

    classes_filter.setCurrentText(year)
    assert class_view.model.rowCount() == 1
    students_filter.setCurrentText(year)
    student_view = window.stack.widget(1)
    assert student_view.model.rowCount() == 0
    student_id = services.students.create(
        {"first_name": "Aina", "last_name": "Rabe", "birth_date": "2010-05-12",
         "class_id": class_id})
    class_view.notify_changed()
    assert student_view.model.rowCount() == 1
    assert student_view.model.row_at(0)["id"] == student_id
    window.close()


def test_class_teacher_choices_follow_school_year_in_form(qapp):
    ctx, services = make_env()
    view = classes_view(services, ctx)
    year_one, year_two = "2030-2031", "2031-2032"
    employee_one = services.teachers.create({
        "employee_no": "ENS2030", "first_name": "Aina", "last_name": "Rabe",
        "gender": "F", "birth_date": "1985-01-01", "hire_date": "2020-09-01",
    })
    services.teachers.assign_year(employee_one, year_one)
    employee_two = services.teachers.create({
        "employee_no": "ENS2031", "first_name": "Miora", "last_name": "Rabe",
        "gender": "F", "birth_date": "1986-01-01", "hire_date": "2020-09-01",
    })
    services.teachers.assign_year(employee_two, year_two)

    dialog = view.dialog_factory("Classe", view.fields, {"school_year": year_one},
                                view, readonly=False)
    year_input = dialog.widgets["school_year"]
    teacher_combo = dialog.widgets["main_teacher_id"]
    assert teacher_combo.findData(employee_one) >= 0
    assert teacher_combo.findData(employee_two) < 0

    year_input.setText(year_two)
    assert teacher_combo.findData(employee_one) < 0
    assert teacher_combo.findData(employee_two) >= 0
    dialog.close()


def test_main_window_is_centered_on_primary_screen(qapp):
    ctx, services = make_env()
    window = MainWindow(services, ctx)
    avail = qapp.primaryScreen().availableGeometry()
    # La fenêtre s'adapte à l'écran : 1000x650 au maximum, jamais plus grande que l'écran.
    assert window.width() == max(min(1000, int(avail.width() * 0.95)), min(800, avail.width()))
    assert window.height() == max(min(650, int(avail.height() * 0.90)), min(500, avail.height()))
    assert window.width() <= max(avail.width(), 800)
    window.show()
    qapp.processEvents()

    center = window.frameGeometry().center()
    screen_center = qapp.primaryScreen().availableGeometry().center()
    assert abs(center.x() - screen_center.x()) <= 3
    assert abs(center.y() - screen_center.y()) <= 3
    window.close()


def test_number_field_uses_configured_precision(qapp):
    dialog = FormDialog("Montant", [Field("amount", "Montant", "number", decimals=0, step=1000)])
    amount = dialog.widgets["amount"]

    assert isinstance(amount, QDoubleSpinBox)
    assert amount.decimals() == 0
    assert amount.singleStep() == 1000
    dialog.close()


def test_table_text_and_headers_align_at_start_except_actions():
    model = RowsModel([("name", "Nom"), ("_actions", "Actions")])
    model.set_rows([{"name": "Aina"}])
    left = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

    assert model.data(model.index(0, 0), Qt.ItemDataRole.TextAlignmentRole) == left
    assert model.data(model.index(0, 1), Qt.ItemDataRole.TextAlignmentRole) == Qt.AlignmentFlag.AlignCenter
    assert model.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.TextAlignmentRole) == left
    assert model.headerData(
        1, Qt.Orientation.Horizontal, Qt.ItemDataRole.TextAlignmentRole) == Qt.AlignmentFlag.AlignCenter


def test_login_focuses_identifier_for_keyboard_input(qapp):
    dialog = LoginDialog(None)
    dialog.show()
    qapp.processEvents()

    assert dialog.user.hasFocus()
    QTest.keyClicks(dialog.user, "admin")
    assert dialog.user.text() == "admin"
    dialog.close()


def test_login_has_modern_plain_text_actions(qapp):
    ctx, services = make_env()
    dialog = LoginDialog(services.auth)

    assert dialog.objectName() == "loginDialog"
    assert dialog.heading.text() == "Bienvenue"
    assert dialog.user.placeholderText() == "Votre identifiant"
    assert dialog.pwd.placeholderText() == "Votre mot de passe"
    assert dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).text() == "Se connecter"
    assert dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel).text() == "Quitter"
    assert all(button.icon().isNull() for button in dialog.buttons.buttons())
    dialog.close()


def test_unexpected_dialog_error_is_handled_and_password_cleared(qapp, monkeypatch):
    class BrokenAuth:
        def login(self, _username, _password):
            raise RuntimeError("internal detail")

    handled = []
    monkeypatch.setattr("app.ui.dialogs.handle_error", lambda parent, exc: handled.append(exc))
    dialog = LoginDialog(BrokenAuth())
    dialog.user.setText("admin")
    dialog.pwd.setText("secret")
    dialog._submit()

    assert len(handled) == 1 and isinstance(handled[0], RuntimeError)
    assert dialog.pwd.text() == ""
    assert not dialog.error.isHidden()
    dialog.close()


def test_confirmation_buttons_have_no_icons(qapp, monkeypatch):
    captured = {}

    def fake_exec(dialog):
        buttons = dialog.buttons()
        captured["texts"] = [button.text() for button in buttons]
        captured["icons_empty"] = all(button.icon().isNull() for button in buttons)
        return 0

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    assert ask_confirmation(None, "Confirmation", "Continuer ?") is False
    assert captured["texts"] == ["Oui", "Non"]
    assert captured["icons_empty"] is True


def test_unexpected_errors_are_logged_without_showing_details(qapp, monkeypatch, caplog):
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: shown.append(args[-1]))
    try:
        raise RuntimeError("sensitive database detail")
    except RuntimeError as exc:
        handle_error(None, exc)

    assert "sensitive database detail" not in shown[0]
    assert "sensitive database detail" in caplog.text


def test_input_and_table_text_are_dark(qapp):
    line = QLineEdit()
    combo = QComboBox()
    table = QTableWidget(1, 1)
    for widget in (line, combo, table):
        widget.ensurePolished()

    assert line.palette().color(line.foregroundRole()).name() == "#1e293b"
    assert combo.palette().color(combo.foregroundRole()).name() == "#1e293b"
    assert table.palette().color(table.foregroundRole()).name() == "#1e293b"
    assert PALETTE["main"] == "#f5f6fb"
    assert "#f5f6fb" in qapp.styleSheet()


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
    assert employee.choices() == [("EMP001 - Rakoto Aina", employee_id)]
    class_name = next(field for field in view.fields if field.name == "name")
    assert "Crèche" in class_name.placeholder and "CE1" in class_name.placeholder


def test_student_form_has_parent_phone_fields(qapp):
    ctx, services = make_env()
    view = students_view(services, ctx)

    fields = {field.name: field.label for field in view.fields}
    assert fields["tutor_phone"] == "Téléphone du tuteur"
    assert fields["father_phone"] == "Téléphone du père"
    assert fields["mother_phone"] == "Téléphone de la mère"
    assert fields["tutor_profession"] == "Profession du tuteur"
    assert fields["father_profession"] == "Profession du père"
    assert fields["mother_profession"] == "Profession de la mère"


def test_tuition_screen_uses_named_activity_fees(qapp):
    ctx, services = make_env()
    view = FeesView(services, ctx)

    activity_fields = [field.label for field in view.fees.fields if field.name.startswith("activity_")]
    assert activity_fields == [
        "Calendrier (Ar)", "Classe verte (Ar)", "Enveloppe (Ar)",
        "Fête de fin d'année (Ar)", "Autre (Ar)"]


def test_payment_history_shows_gender_and_payment_status_without_view_action(qapp):
    ctx, services = make_env()
    view = FeesView(services, ctx)

    columns = {column[0]: column[1] for column in view.history.columns}
    assert columns["class_name"] == "Classe"
    assert columns["school_year"] == "Année scolaire"
    assert columns["gender"] == "Genre"
    assert columns["payment_status"] == "État du paiement"
    assert "cancelled" not in columns
    assert all(column[0] != "_actions" for column in view.history.display_columns)


def test_payment_history_dropdown_filters_by_class_and_school_year(qapp):
    ctx, services = make_env()
    class_ids = []
    for class_name, school_year in (
        ("Classe Filtre A", "2025-2026"), ("Classe Filtre B", "2026-2027")):
        class_id = services.classes.create({"name": class_name, "school_year": school_year})
        services.students.select_school_year(school_year)
        student_id = services.students.create(
            {"first_name": class_name.replace(" ", ""), "last_name": "Rakoto",
             "birth_date": "2010-05-12", "class_id": class_id})
        services.fees.create({"class_id": class_id, "monthly_amount": 0, "droit_amount": 100})
        services.payments.record(
            student_id, {"fee_code": "droit", "amount": 100, "method": "cash"})
        class_ids.append(class_id)

    view = FeesView(services, ctx)
    view.tabs.setCurrentWidget(view.history_tab)
    assert view.history.model.rowCount() == 2
    view.history_class.setCurrentIndex(view.history_class.findData(class_ids[0]))
    assert view.history.model.rowCount() == 1
    assert view.history.model.row_at(0)["class_name"] == "Classe Filtre A"

    view.history_year.setCurrentIndex(view.history_year.findData("2026-2027"))
    assert view.history_class.currentData() is None
    assert view.history.model.rowCount() == 1

    view.history_class.setCurrentIndex(0)
    assert view.history.model.rowCount() == 1
    assert view.history.model.row_at(0)["school_year"] == "2026-2027"


def test_arrears_screen_has_filters_detailed_columns_and_csv_export(qapp):
    ctx, services = make_env()
    view = FeesView(services, ctx)

    arrears = view.arrears
    assert arrears.year_cb.objectName() == "arrearsSchoolYearFilter"
    assert arrears.class_cb.objectName() == "arrearsClassFilter"
    assert arrears.month_cb.objectName() == "arrearsMonthFilter"
    assert arrears.year_cb.itemText(0) == "Toutes les années"
    assert arrears.class_cb.itemText(0) == "Toutes les classes"
    assert arrears.month_cb.itemText(0) == "Tous les mois échus"
    assert arrears.export_btn.text() == "Exporter CSV"
    assert [arrears.table.horizontalHeaderItem(i).text() for i in range(arrears.table.columnCount())] == [
        "Matricule", "Nom", "Prénom", "Sexe", "Classe", "Année scolaire",
        "Poste impayé", "Mois", "Dû", "Payé", "Reste à payer"]
    assert arrears.table.rowCount() == 0
    assert arrears.previous_btn.isEnabled() is False
    assert arrears.next_btn.isEnabled() is False


def test_arrears_table_paginates_large_result_sets(qapp):
    ctx, services = make_env()
    view = FeesView(services, ctx)
    arrears = view.arrears
    def arrears_page(**filters):
        rows = [
            {
            "student_id": index + 1, "matricule": f"MAT{index + 1}",
            "last_name": "Nom", "first_name": f"Prénom {index + 1}", "gender": "M",
            "class_name": "Classe A", "school_year": "2026-2027", "fee_label": "Écolage",
            "month": 9, "due": 1000, "paid": 0, "balance": 1000,
            }
            for index in range(101)
        ]
        page = filters["page"]
        start = page * filters["size"]
        return {
            "rows": rows[start:start + filters["size"]],
            "total": len(rows),
            "students": len(rows),
            "balance": sum(row["balance"] for row in rows),
            "page": page,
            "pages": (len(rows) + filters["size"] - 1) // filters["size"],
        }

    arrears.sv.payments.arrears_page = arrears_page

    arrears.compute()
    assert arrears.table.rowCount() == 100
    assert arrears.previous_btn.isEnabled() is False
    assert arrears.next_btn.isEnabled() is True
    assert "101 poste(s) impayé(s)" in arrears.total.text()

    arrears.next_btn.click()
    assert arrears.table.rowCount() == 1
    assert arrears.page_label.text() == "Page 2 / 2"
    assert arrears.previous_btn.isEnabled() is True
    assert arrears.next_btn.isEnabled() is False
    assert arrears.table.item(0, 0).text() == "MAT101"


def test_arrears_are_loaded_only_after_explicit_request(qapp):
    ctx, services = make_env()
    view = FeesView(services, ctx)
    arrears = view.arrears
    calls = []
    arrears.sv.payments.arrears_page = lambda **_filters: calls.append(True) or {
        "rows": [], "total": 0, "students": 0, "balance": 0, "page": 0, "pages": 1,
    }

    view.tabs.setCurrentWidget(arrears)
    view.refresh()
    assert calls == []
    assert "cliquez sur" in arrears.total.text()

    arrears.compute_btn.click()
    assert calls == [True]


def test_salary_screen_has_base_and_disbursement_submenus(qapp):
    ctx, services = make_env()
    view = SalariesView(services, ctx)

    assert [view.tabs.tabText(i) for i in range(view.tabs.count())] == [
        "Rémunérations de base", "Historique des sorties"]
    assert [column[0] for column in view.history_view.columns] == [
        "employee_no", "employee_name", "position", "title", "payout_date",
        "school_year", "hours", "hourly_rate", "amount"]


def test_salary_base_defaults_professors_to_hourly(qapp):
    ctx, services = make_env()
    professor_id = services.teachers.create({
        "employee_no": "PROF001", "first_name": "Mamy", "last_name": "Rabe",
        "gender": "M", "birth_date": "1980-01-01", "hire_date": "2010-01-01",
        "position": "Professeur",
    })
    teacher_id = services.teachers.create({
        "employee_no": "ENS001", "first_name": "Aina", "last_name": "Rakoto",
        "gender": "F", "birth_date": "1985-01-01", "hire_date": "2010-01-01",
        "position": "Maîtresse",
    })
    view = SalariesView(services, ctx)
    dialog = SalaryBaseDialog(
        "Ajouter : rémunération", view.base_view.fields, {}, view.base_view,
        salaries=services.salaries)

    dialog.widgets["employee_id"].setCurrentIndex(
        dialog.widgets["employee_id"].findData(professor_id))
    assert "pay_type" not in dialog.widgets
    assert not dialog.widgets["hourly_rate"].isHidden()
    assert dialog.widgets["monthly_amount"].isHidden()
    dialog.widgets["employee_id"].setCurrentIndex(
        dialog.widgets["employee_id"].findData(teacher_id))
    assert dialog.widgets["monthly_amount"].isHidden() is False
    assert dialog.widgets["hourly_rate"].isHidden()
    dialog.widgets["employee_id"].setCurrentIndex(
        dialog.widgets["employee_id"].findData(professor_id))
    assert dialog.widgets["hourly_rate"].isHidden() is False
