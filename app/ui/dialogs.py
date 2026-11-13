from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout)

from app.core.exceptions import AppError


class _BaseDialog(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(380)
        self.form = QFormLayout()
        self.error = QLabel()
        self.error.setStyleSheet("color: #b00020;")
        self.error.setWordWrap(True)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self._submit)
        self.buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(self.form)
        layout.addWidget(self.error)
        layout.addWidget(self.buttons)

    @staticmethod
    def _line(password=False, max_len=128):
        w = QLineEdit()
        w.setMaxLength(max_len)
        if password:
            w.setEchoMode(QLineEdit.EchoMode.Password)
        return w

    def _submit(self):
        try:
            self.on_submit()
        except AppError as e:
            self.error.setText(str(e))
            return
        self.accept()

    def on_submit(self):
        raise NotImplementedError


class LoginDialog(_BaseDialog):
    def __init__(self, auth):
        super().__init__("Connexion - Gestion d'école")
        self.auth = auth
        self.user, self.pwd = self._line(max_len=50), self._line(True)
        self.form.addRow("Identifiant", self.user)
        self.form.addRow("Mot de passe", self.pwd)
        self.user.setFocus()

    def on_submit(self):
        try:
            self.auth.login(self.user.text(), self.pwd.text())
        finally:
            self.pwd.clear()


class SetupDialog(_BaseDialog):
    """Premier lancement : création de l'administrateur (aucun mot de passe par défaut)."""

    def __init__(self, auth):
        super().__init__("Première configuration — compte administrateur")
        self.auth = auth
        self.name, self.user = self._line(max_len=100), self._line(max_len=50)
        self.pwd, self.pwd2 = self._line(True), self._line(True)
        for label, w in (("Nom complet", self.name), ("Identifiant", self.user),
                         ("Mot de passe", self.pwd), ("Confirmation", self.pwd2)):
            self.form.addRow(label, w)

    def on_submit(self):
        if self.pwd.text() != self.pwd2.text():
            from app.core.exceptions import ValidationError
            raise ValidationError("Les mots de passe ne correspondent pas.")
        self.auth.bootstrap_admin(self.user.text(), self.name.text(), self.pwd.text())


class ChangePasswordDialog(_BaseDialog):
    def __init__(self, auth, forced=False):
        super().__init__("Changement de mot de passe")
        self.auth = auth
        if forced:
            self.form.addRow(QLabel("Vous devez choisir un nouveau mot de passe."))
        self.old, self.new, self.new2 = self._line(True), self._line(True), self._line(True)
        for label, w in (("Mot de passe actuel", self.old), ("Nouveau", self.new), ("Confirmation", self.new2)):
            self.form.addRow(label, w)

    def on_submit(self):
        if self.new.text() != self.new2.text():
            from app.core.exceptions import ValidationError
            raise ValidationError("Les mots de passe ne correspondent pas.")
        self.auth.change_password(self.old.text(), self.new.text())
