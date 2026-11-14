from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout, QFrame, QLabel,
                             QLineEdit, QVBoxLayout)

from app import config
from app.core.exceptions import AppError, ValidationError
from app.ui.utils import handle_error


class _BaseDialog(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setObjectName("appDialog")
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        self.heading = QLabel(title)
        self.heading.setObjectName("dialogTitle")
        self.subtitle = QLabel("Gestion d'école")
        self.subtitle.setObjectName("dialogSubtitle")
        self.form = QFormLayout()
        self.error = QLabel()
        self.error.setObjectName("dialogError")
        self.error.setWordWrap(True)
        self.error.hide()
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Valider")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Annuler")
        for button in self.buttons.buttons():
            button.setIcon(QIcon())
        self.buttons.accepted.connect(self._submit)
        self.buttons.rejected.connect(self.reject)

        card = QFrame()
        card.setObjectName("dialogCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 22, 24, 22)
        card_layout.setSpacing(16)
        card_layout.addLayout(self.form)
        card_layout.addWidget(self.error)
        card_layout.addWidget(self.buttons)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(4)
        layout.addWidget(self.heading)
        layout.addWidget(self.subtitle)
        layout.addSpacing(10)
        layout.addWidget(card)

    @staticmethod
    def _line(password=False, max_len=128):
        widget = QLineEdit()
        widget.setMaxLength(max_len)
        if password:
            widget.setEchoMode(QLineEdit.EchoMode.Password)
        return widget

    def _submit(self):
        try:
            self.on_submit()
        except AppError as exc:
            self.error.setText(str(exc))
            self.error.show()
            return
        except Exception as exc:
            self.error.setText("Une erreur inattendue est survenue. Réessayez ou consultez le journal.")
            self.error.show()
            handle_error(self, exc)
            return
        self.accept()

    def on_submit(self):
        raise NotImplementedError


class SchoolDialog(_BaseDialog):
    """Sélection de l'école à gérer : chaque établissement a ses données isolées."""

    def __init__(self):
        super().__init__("Choix de l'établissement")
        self.subtitle.setText("Sélectionnez l'école à gérer.")
        self.combo = QComboBox()
        self.combo.addItems(config.SCHOOLS)
        self.form.addRow("École", self.combo)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Ouvrir")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Quitter")

    def on_submit(self):
        config.use_school(self.combo.currentIndex())


class LoginDialog(_BaseDialog):
    def __init__(self, auth):
        super().__init__("Connexion à SchoolManager")
        self.setObjectName("loginDialog")
        self.auth = auth
        self.heading.setText("Bienvenue")
        self.subtitle.setText("Connectez-vous pour gérer votre établissement.")
        self.user = self._line(max_len=50)
        self.user.setObjectName("loginUser")
        self.user.setPlaceholderText("Votre identifiant")
        self.pwd = self._line(password=True)
        self.pwd.setObjectName("loginPassword")
        self.pwd.setPlaceholderText("Votre mot de passe")
        self.form.addRow("Identifiant", self.user)
        self.form.addRow("Mot de passe", self.pwd)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Se connecter")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Quitter")
        self.user.setFocus()

    def on_submit(self):
        try:
            self.auth.login(self.user.text(), self.pwd.text())
        finally:
            self.pwd.clear()


class SetupDialog(_BaseDialog):
    """Premier lancement : création de l'administrateur (aucun mot de passe par défaut)."""

    def __init__(self, auth):
        super().__init__("Première configuration")
        self.auth = auth
        self.subtitle.setText("Créez le compte administrateur de votre établissement.")
        self.name, self.user = self._line(max_len=100), self._line(max_len=50)
        self.pwd, self.pwd2 = self._line(True), self._line(True)
        self.pwd.setPlaceholderText("Mot de passe sécurisé")
        self.pwd2.setPlaceholderText("Saisissez à nouveau le mot de passe")
        for label, widget in (("Nom complet", self.name), ("Identifiant", self.user),
                              ("Mot de passe", self.pwd), ("Confirmation", self.pwd2)):
            self.form.addRow(label, widget)

    def on_submit(self):
        if self.pwd.text() != self.pwd2.text():
            raise ValidationError("Les mots de passe ne correspondent pas.")
        self.auth.bootstrap_admin(self.user.text(), self.name.text(), self.pwd.text())


class ChangePasswordDialog(_BaseDialog):
    def __init__(self, auth, forced=False):
        super().__init__("Changement de mot de passe")
        self.auth = auth
        self.subtitle.setText("Choisissez un nouveau mot de passe sécurisé.")
        if forced:
            self.form.addRow(QLabel("Vous devez choisir un nouveau mot de passe."))
        self.old, self.new, self.new2 = self._line(True), self._line(True), self._line(True)
        for label, widget in (("Mot de passe actuel", self.old), ("Nouveau", self.new),
                              ("Confirmation", self.new2)):
            self.form.addRow(label, widget)

    def on_submit(self):
        if self.new.text() != self.new2.text():
            raise ValidationError("Les mots de passe ne correspondent pas.")
        self.auth.change_password(self.old.text(), self.new.text())
