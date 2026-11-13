"""Exceptions métier : leur message est affichable à l'utilisateur."""


class AppError(Exception):
    """Erreur métier de base."""


class ValidationError(AppError):
    pass


class AuthenticationError(AppError):
    pass


class PermissionDenied(AppError):
    pass


class NotFoundError(AppError):
    pass


class DuplicateError(AppError):
    pass
