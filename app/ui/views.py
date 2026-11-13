"""Définition déclarative des écrans (colonnes + formulaires) : ajouter un module = ajouter une fonction."""
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from app.core.permissions import ROLE_LABELS
from app.core import school
from app.ui.crud_view import CrudView
from app.ui.forms import Field
from app.ui.utils import LABELS

GENDERS = lambda: [("Masculin", "M"), ("Féminin", "F")]
STATUS = lambda: [(v, k) for k, v in LABELS["status"].items()]
ROLES = lambda: [(v, k) for k, v in ROLE_LABELS.items()]
ACTIVE = lambda: [("Actif", 1), ("Inactif", 0)]


def students_view(sv, ctx):
    columns = [("matricule", "Matricule"), ("last_name", "Nom"), ("first_name", "Prénom"),
               ("birth_date", "Naissance"), ("class_name", "Classe"), ("status", "Statut", LABELS["status"])]
    fields = [Field("matricule", "Matricule (auto si vide)", max_len=20),
              Field("last_name", "Nom", required=True, max_len=60),
              Field("first_name", "Prénom", required=True, max_len=60),
              Field("birth_date", "Date de naissance", "date", required=True),
              Field("gender", "Genre", "combo", choices=GENDERS),
              Field("guardian_name", "Responsable légal", max_len=100),
              Field("tuition_discount", "Remise d'écolage (%)", "number", maximum=100, decimals=0, step=1,
                    default=0),
              Field("address", "Adresse", max_len=200),
              Field("class_id", "Classe", "combo", choices=sv.classes.options),
              Field("status", "Statut", "combo", required=True, choices=STATUS)]

    def import_csv(view):
        path, _ = QFileDialog.getOpenFileName(view, "Importer des élèves", "", "CSV (*.csv)")
        if path:
            r = sv.students.import_csv(path)
            detail = "\n".join(f"Ligne {n} : {m}" for n, m in r.errors[:10])
            QMessageBox.information(view, "Import terminé", f"{r.inserted} ajoutés, {r.duplicates} doublons, "
                                    f"{len(r.errors)} erreurs.\n{detail}")
            view.refresh()

    def export_csv(view):
        path, _ = QFileDialog.getSaveFileName(view, "Exporter les élèves", "eleves.csv", "CSV (*.csv)")
        if path:
            n = sv.students.export_csv(path, view.search.text())
            QMessageBox.information(view, "Export", f"{n} ligne(s) exportée(s).")

    return CrudView(sv.students, columns, fields, ctx, noun="élève", extra_actions=[
        ("Importer CSV", import_csv, "students.import"), ("Exporter CSV", export_csv, "students.export")])


def teachers_view(sv, ctx):
    columns = [("employee_no", "N°"), ("last_name", "Nom"), ("first_name", "Prénom"),
               ("speciality", "Spécialité"), ("email", "E-mail")]
    fields = [Field("employee_no", "N° employé", required=True, max_len=20),
              Field("last_name", "Nom", required=True, max_len=60),
              Field("first_name", "Prénom", required=True, max_len=60),
              Field("email", "E-mail", max_len=120), Field("phone", "Téléphone", max_len=20),
              Field("speciality", "Spécialité", max_len=80),
              Field("hire_date", "Date d'embauche", "date", required=True)]
    return CrudView(sv.teachers, columns, fields, ctx, noun="enseignant")


def classes_view(sv, ctx):
    columns = [("name", "Classe"), ("level", "Niveau"), ("school_year", "Année"),
               ("student_count", "Élèves"), ("capacity", "Effectif max."), ("main_teacher", "Titulaire")]
    fields = [Field("name", "Nom", required=True, max_len=40),
              Field("level", "Niveau", "combo", choices=lambda: [(level, level) for level in school.LEVELS]),
              Field("school_year", "Année scolaire (AAAA-AAAA)", required=True, max_len=9),
              Field("capacity", "Effectif maximal", "number", minimum=1, maximum=80, decimals=0, step=1,
                    default=45),
              Field("main_teacher_id", "Titulaire", "combo", choices=sv.teachers.options
                    if ctx.session.can("teachers.read") else None)]
    return CrudView(sv.classes, columns, fields, ctx, noun="classe")


def subjects_view(sv, ctx):
    columns = [("code", "Code"), ("name", "Matière"), ("coefficient", "Coef."), ("teacher_name", "Enseignant")]
    fields = [Field("code", "Code", required=True, max_len=20), Field("name", "Nom", required=True, max_len=80),
              Field("coefficient", "Coefficient", "number", required=True, minimum=0.5, maximum=20),
              Field("teacher_id", "Enseignant", "combo", choices=sv.teachers.options
                    if ctx.session.can("teachers.read") else None)]
    return CrudView(sv.subjects, columns, fields, ctx, noun="matière")


def users_view(sv, ctx):
    columns = [("username", "Identifiant"), ("full_name", "Nom"), ("role", "Rôle", LABELS["role"]),
               ("is_active", "Statut", LABELS["is_active"])]
    fields = [Field("username", "Identifiant", required=True, max_len=50),
              Field("full_name", "Nom complet", required=True),
              Field("role", "Rôle", "combo", required=True, choices=ROLES),
              Field("is_active", "Statut", "combo", required=True, choices=ACTIVE),
              Field("password", "Mot de passe", "password")]
    return CrudView(sv.users, columns, fields, ctx, noun="utilisateur")


def audit_view(sv, ctx):
    columns = [("ts", "Date (UTC)"), ("username", "Utilisateur"), ("action", "Action"),
               ("entity", "Entité"), ("entity_id", "ID"), ("details", "Détails")]
    return CrudView(sv.audit, columns, [], ctx, noun="événement", read_only=True)
