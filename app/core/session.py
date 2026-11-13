"""Session utilisateur : identité, expiration par inactivité, vérification des permissions."""
import time
from dataclasses import dataclass

from app.core.exceptions import AuthenticationError, PermissionDenied
from app.core.permissions import ROLE_PERMISSIONS


@dataclass(frozen=True)
class CurrentUser:
    id: int
    username: str
    full_name: str
    role: str
    must_change_password: bool = False


class Session:
    def __init__(self, timeout_seconds: int):
        self.timeout = timeout_seconds
        self.user = None
        self._last = time.monotonic()

    def login(self, user: CurrentUser) -> None:
        self.user = user
        self._last = time.monotonic()

    def logout(self) -> None:
        self.user = None

    @property
    def expired(self) -> bool:
        return self.user is not None and (time.monotonic() - self._last) > self.timeout

    def touch(self) -> None:
        if self.user is not None and not self.expired:
            self._last = time.monotonic()

    def can(self, permission: str) -> bool:
        return (self.user is not None and not self.expired
                and permission in ROLE_PERMISSIONS.get(self.user.role, ()))

    def require(self, permission: str) -> CurrentUser:
        if self.user is None:
            raise AuthenticationError("Authentification requise.")
        if self.expired:
            raise AuthenticationError("Session expirée, veuillez vous reconnecter.")
        if permission not in ROLE_PERMISSIONS.get(self.user.role, ()):
            raise PermissionDenied("Vous n'avez pas le droit d'effectuer cette action.")
        self._last = time.monotonic()
        return self.user
