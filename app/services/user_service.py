from app.core import security
from app.core import validators as V
from app.core.exceptions import ValidationError
from app.core.session import CurrentUser
from app.repositories.repos import UserRepository
from app.services.base import CrudService


class UserService(CrudService):
    entity = "users"
    repo_cls = UserRepository
    db_attr = "accounts"           # les comptes sont communs aux trois écoles
    read_perm = write_perm = delete_perm = "users.manage"

    def validate(self, data):
        password = data.get("password") or None
        if password:
            security.check_password_policy(password)
        return {
            "username": V.text(data, "username", "Identifiant", pattern=V.USERNAME_RE,
                               error="Identifiant : 3 à 50 caractères (lettres, chiffres, . _ -)."),
            "full_name": V.text(data, "full_name", "Nom complet"),
            "role": V.choice(data, "role", "Rôle", ("admin", "secretary", "teacher")),
            "is_active": int(V.choice(data, "is_active", "Statut", (0, 1, "0", "1"), default=1)),
            "password": password,
        }

    def prepare(self, clean):
        password = clean.pop("password", None)
        if password:
            clean["password_hash"] = security.hash_password(password)
            clean["must_change_password"] = 1   # mot de passe défini par un admin => à changer
        return clean

    def _keep_one_admin(self, user_id, role, active):
        if (role != "admin" or not active) and self.repo.count_active_admins(user_id) == 0:
            raise ValidationError("Il doit rester au moins un administrateur actif.")

    def create(self, data):
        if not data.get("password"):
            raise ValidationError("Le mot de passe est obligatoire.")
        return super().create(data)

    def update(self, id_, data):
        self.ctx.session.require(self.write_perm)
        clean = self.validate(data)
        self._keep_one_admin(id_, clean["role"], clean["is_active"])
        super().update(id_, data)
        self._sync_own_session(id_)

    def _sync_own_session(self, id_):
        """Si l'utilisateur modifie son propre compte, la session reflète aussitôt
        le nouveau rôle/état (sinon il conserverait ses droits jusqu'à reconnexion)."""
        session = self.ctx.session
        if session.user is None or session.user.id != id_:
            return
        row = self.repo.get(id_)
        if row is None or not row["is_active"]:
            session.logout()
            return
        session.login(CurrentUser(
            row["id"], row["username"], row["full_name"], row["role"],
            bool(row["must_change_password"])))

    def delete(self, id_):
        self.ctx.session.require(self.delete_perm)
        if self.user and self.user.id == id_:
            raise ValidationError("Vous ne pouvez pas supprimer votre propre compte.")
        self._keep_one_admin(id_, None, 0)
        super().delete(id_)
