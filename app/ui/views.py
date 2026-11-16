from PyQt6.QtCore import QSignalBlocker
from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox, QComboBox, QLabel

from app.core import school
from app.core.permissions import ROLE_LABELS
from app.ui.crud_view import CrudView
from app.ui.forms import Field, FormDialog
from app.ui.salaries_view import SalariesView
from app.ui.utils import LABELS, ask_confirmation

GENDERS = lambda: [("Masculin", "M"), ("Féminin", "F")]
STATUS = lambda: [(v, k) for k, v in LABELS["status"].items()]
ROLES = lambda: [(v, k) for k, v in ROLE_LABELS.items()]
ACTIVE = lambda: [("Actif", 1), ("Inactif", 0)]
ATTENDANCE_STATUS = lambda: [(v, k) for k, v in LABELS["attendance_status"].items()]


class _ClassDialog(FormDialog):
    def __init__(self, title, fields, initial, parent, readonly=False, *, teachers, can_read_teachers):
        self.teachers = teachers
        self.can_read_teachers = can_read_teachers
        self.initial_teacher_id = (initial or {}).get("main_teacher_id")
        super().__init__(title, fields, initial, parent, readonly=readonly)
        self.widgets["school_year"].textChanged.connect(self._sync_teachers)
        self._sync_teachers()

    def _sync_teachers(self):
        combo = self.widgets["main_teacher_id"]
        selected = combo.currentData()
        if selected is None:
            selected = self.initial_teacher_id
        year = self.widgets["school_year"].text().strip()
        options = self.teachers.options_for_year(year) if self.can_read_teachers and year else []
        blocker = QSignalBlocker(combo)
        combo.clear()
        combo.addItem("- Aucun -", None)
        for label, employee_id in options:
            combo.addItem(label, employee_id)
        index = combo.findData(selected)
        combo.setCurrentIndex(index if index >= 0 else 0)
        self.initial_teacher_id = None
        del blocker


def _sync_year_filter(combo, options, selected):
    values = list(options)
    if values == [combo.itemText(i) for i in range(combo.count())] and \
            combo.currentText() == selected:
        return selected
    blocker = QSignalBlocker(combo)
    combo.clear()
    combo.addItems(values)
    index = combo.findText(selected)
    if index < 0 and combo.count():
        index = 0
    if index >= 0:
        combo.setCurrentIndex(index)
    result = combo.currentText()
    del blocker
    return result


def students_view(sv, ctx, on_change=None):
    years = QComboBox()
    years.setObjectName("studentsSchoolYearFilter")
    years.addItems(sv.students.school_year_options())
    sv.students.select_school_year(years.currentText())
    year_filter = QLabel("Année scolaire")

    columns = [("matricule", "Matricule"), ("last_name", "Nom"), ("first_name", "Prénom"),
               ("birth_date", "Naissance"), ("class_name", "Classe"), ("status", "Statut", LABELS["status"])]
    fields = [Field("matricule", "Matricule (auto si vide)", max_len=20),
              Field("last_name", "Nom", required=True, max_len=60),
              Field("first_name", "Prénom", required=True, max_len=60),
              Field("birth_date", "Date de naissance", "date", required=True),
              Field("gender", "Genre", "combo", choices=GENDERS),
              Field("tutor_name", "Tuteur", max_len=100),
              Field("tutor_phone", "Téléphone du tuteur", max_len=20),
              Field("tutor_profession", "Profession du tuteur", max_len=100),
              Field("father_name", "Nom du père", max_len=100),
              Field("father_phone", "Téléphone du père", max_len=20),
              Field("father_profession", "Profession du père", max_len=100),
              Field("mother_name", "Nom de la mère", max_len=100),
              Field("mother_phone", "Téléphone de la mère", max_len=20),
              Field("mother_profession", "Profession de la mère", max_len=100),
              Field("tuition_discount", "Remise d'écolage (%)", "number", maximum=100, decimals=0, step=1, default=0),
              Field("address", "Adresse", max_len=200),
              Field("class_id", "Classe", "combo",
                    choices=lambda: sv.classes.repo.options_for_year(sv.students.school_year)),
              Field("status", "Statut", "combo", required=True, choices=STATUS)]

    def import_csv(view):
        path, _ = QFileDialog.getOpenFileName(view, "Importer des élèves", "", "CSV (*.csv)")
        if path:
            r = sv.students.import_csv(path)
            detail = "\n".join(f"Ligne {n} : {m}" for n, m in r.errors[:10])
            QMessageBox.information(view, "Import terminé", f"{r.inserted} ajoutés, {r.duplicates} doublons, {len(r.errors)} erreurs.\n{detail}")
            view.notify_changed()

    def export_csv(view):
        path, _ = QFileDialog.getSaveFileName(view, "Exporter les élèves", "eleves.csv", "CSV (*.csv)")
        if path:
            n = sv.students.export_csv(path, view.search.text())
            QMessageBox.information(view, "Export", f"{n} ligne(s) exportée(s).")

    def enroll_selected(view):
        student_id = view._row_id()
        if student_id is None:
            return
        classes = [item for item in sv.classes.class_year_options()
                   if item[2] != sv.students.school_year]
        if not classes:
            QMessageBox.information(view, "Inscription", "Aucune autre année scolaire n'a de classe.")
            return
        label, ok = QInputDialog.getItem(
            view, "Nouvelle inscription", "Classe de destination :",
            [item[0] for item in classes], 0, False)
        if not ok:
            return
        selected = next((item for item in classes if item[0] == label), None)
        if selected is None:
            return
        _, class_id, school_year = selected
        sv.students.enroll_existing(student_id, class_id, school_year)
        view.notify_changed()

    def unenroll_selected(view):
        student_id = view._row_id()
        if student_id is None:
            return
        if ask_confirmation(view, "Confirmation",
                            f"Retirer cet élève de l'année {sv.students.school_year} ?"):
            sv.students.unenroll(student_id, sv.students.school_year)
            view.notify_changed()

    view = CrudView(sv.students, columns, fields, ctx, noun="élève", top_controls=[
        year_filter, years], extra_actions=[
        ("Réinscrire l'élève sélectionné", enroll_selected, "students.write"),
        ("Retirer de cette année", unenroll_selected, "students.write"),
        ("Importer CSV", import_csv, "students.import"),
        ("Exporter CSV", export_csv, "students.export")], on_change=on_change)

    def refresh_filters():
        selected = _sync_year_filter(
            years, sv.students.school_year_options(), sv.students.school_year)
        if selected != sv.students.school_year:
            view.page_no = 0
        sv.students.select_school_year(selected)

    def select_year(value):
        sv.students.select_school_year(value)
        view.page_no = 0
        if on_change:
            on_change()
        else:
            view.page_no = 0
            view.refresh()

    view.refresh_filters = refresh_filters
    years.currentTextChanged.connect(select_year)
    return view


def teachers_view(sv, ctx, on_change=None):
    years = QComboBox()
    years.setObjectName("teachersSchoolYearFilter")
    years.addItems(sv.teachers.school_year_options())
    sv.teachers.select_school_year(years.currentText())

    columns = [("employee_no", "Numéro"), ("last_name", "Nom"), ("first_name", "Prénoms"),
               ("gender", "Genre", LABELS["gender"]), ("birth_date", "Date de naissance"),
               ("birth_place", "Lieu de naissance"), ("phone", "Téléphone"), ("address", "Adresse"),
               ("position", "Poste"), ("hire_date", "Date d'embauche")]
    fields = [Field("employee_no", "Numéro", required=True, max_len=20),
              Field("last_name", "Nom", required=True, max_len=60),
              Field("first_name", "Prénoms", required=True, max_len=60),
              Field("gender", "Genre", "combo", required=True, choices=GENDERS),
              Field("birth_date", "Date de naissance", "date", required=True),
              Field("birth_place", "Lieu de naissance", max_len=100),
              Field("phone", "Téléphone", max_len=20),
              Field("address", "Adresse", max_len=200),
              Field("position", "Poste", max_len=80),
              Field("hire_date", "Date d'embauche", "date", required=True)]
    def assign_selected(view):
        employee_id = view._row_id()
        if employee_id is None:
            return
        classes = [item for item in sv.classes.class_year_options()
                   if item[2] != sv.teachers.school_year]
        if not classes:
            QMessageBox.information(view, "Affectation", "Aucune classe d'une autre année scolaire.")
            return
        label, ok = QInputDialog.getItem(
            view, "Affecter l'employé", "Classe de l'année souhaitée :",
            [item[0] for item in classes], 0, False)
        if ok:
            selected = next((item for item in classes if item[0] == label), None)
            if selected is None:
                return
            sv.teachers.assign_year(employee_id, selected[2])
            view.notify_changed()

    def remove_selected_assignment(view):
        employee_id = view._row_id()
        if employee_id is None:
            return
        if ask_confirmation(view, "Confirmation",
                            f"Retirer cet employé de l'année {sv.teachers.school_year} ?"):
            sv.teachers.remove_year(employee_id, sv.teachers.school_year)
            view.notify_changed()

    view = CrudView(sv.teachers, columns, fields, ctx, noun="employé",
                    top_controls=[QLabel("Année scolaire"), years],
                    extra_actions=[
                        ("Affecter à une autre année", assign_selected, "teachers.write"),
                        ("Retirer de cette année", remove_selected_assignment, "teachers.write")],
                    on_change=on_change)

    def refresh_filters():
        selected = _sync_year_filter(
            years, sv.teachers.school_year_options(), sv.teachers.school_year)
        if selected != sv.teachers.school_year:
            view.page_no = 0
        sv.teachers.select_school_year(selected)

    def select_year(value):
        sv.teachers.select_school_year(value)
        view.page_no = 0
        if on_change:
            on_change()
        else:
            view.page_no = 0
            view.refresh()

    view.refresh_filters = refresh_filters
    years.currentTextChanged.connect(select_year)
    return view


def classes_view(sv, ctx, on_change=None):
    years = QComboBox()
    years.setObjectName("classesSchoolYearFilter")
    years.addItems(sv.classes.school_year_options())
    sv.classes.select_school_year(years.currentText())
    columns = [("name", "Classe"), ("school_year", "Année"), ("student_count", "Élèves"),
               ("capacity", "Effectif max."), ("employee", "Employé")]
    fields = [Field("name", "Classe / niveau", required=True, max_len=40,
                    placeholder="Crèche, Garderie, PS, MS, GS, CP, CE1…"),
              Field("school_year", "Année scolaire (AAAA-AAAA)", required=True, max_len=9),
              Field("capacity", "Effectif maximal", "number", minimum=1, maximum=80, decimals=0, step=1, default=45),
              Field("main_teacher_id", "Employé", "combo",
                    choices=(lambda: sv.teachers.options_for_year(sv.classes.school_year)
                             if ctx.session.can("teachers.read") else []))]
    view = CrudView(sv.classes, columns, fields, ctx, noun="classe",
                    top_controls=[QLabel("Année scolaire"), years],
                    dialog_factory=lambda title, dialog_fields, initial, parent, readonly=False:
                        _ClassDialog(title, dialog_fields, initial, parent, readonly=readonly,
                                     teachers=sv.teachers,
                                     can_read_teachers=ctx.session.can("teachers.read")),
                    on_change=on_change)

    def refresh_filters():
        selected = _sync_year_filter(
            years, sv.classes.school_year_options(), sv.classes.school_year)
        if selected != sv.classes.school_year:
            view.page_no = 0
        sv.classes.select_school_year(selected)

    def select_year(value):
        sv.classes.select_school_year(value)
        view.page_no = 0
        if on_change:
            on_change()
        else:
            view.page_no = 0
            view.refresh()

    view.refresh_filters = refresh_filters
    years.currentTextChanged.connect(select_year)
    return view


def attendance_view(sv, ctx, on_change=None):
    columns = [("attendance_date", "Date"), ("employee_label", "Employé"),
               ("status", "Statut", LABELS["attendance_status"]),
               ("arrival_time", "Arrivée"), ("departure_time", "Départ"), ("comment", "Commentaire")]
    fields = [    Field("employee_id", "Employé", "combo", required=True,
          choices=(lambda: sv.teachers.options_for_year(sv.teachers.school_year)
                   if ctx.session.can("teachers.read") else [])),
              Field("attendance_date", "Date de pointage", "date", required=True),
              Field("status", "Statut", "combo", required=True, choices=ATTENDANCE_STATUS),
              Field("arrival_time", "Heure d'arrivée (HH:MM)", max_len=5),
              Field("departure_time", "Heure de départ (HH:MM)", max_len=5),
              Field("comment", "Commentaire", max_len=200)]
    return CrudView(sv.attendance, columns, fields, ctx, noun="pointage", on_change=on_change)


def salaries_view(sv, ctx, on_change=None):
    return SalariesView(sv, ctx, on_change)


def expenses_view(sv, ctx, on_change=None):
    columns = [("expense_date", "Date"),
               ("category", "Catégorie", school.EXPENSE_CATEGORIES),
               ("label", "Libellé"), ("amount", "Montant (Ar)"),
               ("created_by_name", "Saisi par")]
    fields = [Field("category", "Catégorie", "combo", required=True,
                    choices=lambda: [(v, k) for k, v in school.EXPENSE_CATEGORIES.items()]),
              Field("label", "Libellé (fournisseur, référence…)", max_len=120),
              Field("amount", "Montant (Ar)", "number", required=True, minimum=1,
                    maximum=school.MAX_AMOUNT, decimals=0, step=1000),
              Field("expense_date", "Date", "date", required=True)]
    return CrudView(sv.expenses, columns, fields, ctx, noun="charge", on_change=on_change)


def users_view(sv, ctx, on_change=None):
    columns = [("username", "Identifiant"), ("full_name", "Nom"), ("role", "Rôle", LABELS["role"]),
               ("is_active", "Statut", LABELS["is_active"])]
    fields = [Field("username", "Identifiant", required=True, max_len=50),
              Field("full_name", "Nom complet", required=True),
              Field("role", "Rôle", "combo", required=True, choices=ROLES),
              Field("is_active", "Statut", "combo", required=True, choices=ACTIVE),
              Field("password", "Mot de passe", "password")]
    return CrudView(sv.users, columns, fields, ctx, noun="utilisateur", on_change=on_change)
