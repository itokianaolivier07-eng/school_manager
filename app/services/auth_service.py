"""Authentification : verrouillage anti brute-force et anti-énumération."""
import time

from app import config
from app.core import security
from app.core.exceptions import AuthenticationError, PermissionDenied, ValidationError
from app.core.session import CurrentUser
from app.core import validators as V
from app.repositories.repos import UserRepository

GENERIC_ERROR = "Identifiants incorrects."


class AuthService:
    def __init__(self, ctx):
        self.ctx = ctx
        self.db = ctx.db
        self.users = UserRepository(ctx.db)

    def has_users(self) -> bool:
        return self.users.count_all() > 0

    def bootstrap_admin(self, username, full_name, password) -> None:
        """Création du premier administrateur (impossible dès qu'un utilisateur existe)."""
        data = {"username": username, "full_name": full_name}
        username = V.text(data, "username", "Identifiant", pattern=V.USERNAME_RE,
                          error="Identifiant : 3 à 50 caractères (lettres, chiffres, . _ -).")
        full_name = V.text(data, "full_name", "Nom complet")
        security.check_password_policy(password)
        with self.db.transaction():
            if self.has_users():
                raise PermissionDenied("Un administrateur existe déjà.")
            self.users.insert({"username": username, "full_name": full_name, "role": "admin",
                               "password_hash": security.hash_password(password)})

    def login(self, username: str, password: str) -> CurrentUser:
        username = (username or "").strip()[:50]
        password = (password or "")[:128]
        row = self.users.get_by_username(username) if username else None
        now = time.time()

        if row is None or not row["is_active"]:
            security.verify_password(password, security.DUMMY_HASH)  # même durée de calcul
            raise AuthenticationError(GENERIC_ERROR)

        if row["locked_until"] and row["locked_until"] > now:
            minutes = int((row["locked_until"] - now) // 60) + 1
            raise AuthenticationError(f"Compte verrouillé. Réessayez dans {minutes} min.")

        if not security.verify_password(password, row["password_hash"]):
            with self.db.transaction():
                self.users.register_failure(row["id"], config.MAX_FAILED_LOGINS,
                                            now + config.LOCKOUT_SECONDS)
            raise AuthenticationError(GENERIC_ERROR)

        with self.db.transaction():
            self.users.reset_failures(row["id"])
            user = CurrentUser(row["id"], row["username"], row["full_name"], row["role"],
                               bool(row["must_change_password"]))
        self.ctx.session.login(user)
        return user

    def logout(self) -> None:
        self.ctx.session.logout()

    def change_password(self, old: str, new: str) -> None:
        user = self.ctx.session.user
        if user is None or self.ctx.session.expired:
            raise AuthenticationError("Authentification requise.")
        row = self.users.get_by_username(user.username)
        if not security.verify_password(old, row["password_hash"]):
            raise AuthenticationError("Ancien mot de passe incorrect.")
        if old == new:
            raise ValidationError("Le nouveau mot de passe doit être différent.")
        security.check_password_policy(new)
        with self.db.transaction():
            self.users.set_password(user.id, security.hash_password(new), must_change=False)
        self.ctx.session.login(CurrentUser(user.id, user.username, user.full_name, user.role, False))
