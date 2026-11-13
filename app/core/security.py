"""Hachage des mots de passe (scrypt, bibliothèque standard) et politique de mots de passe."""
import hashlib
import hmac
import os
import re

from app import config
from app.core.exceptions import ValidationError

_N, _R, _P = 2**14, 8, 1
_MAXMEM = 64 * 1024 * 1024


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32, maxmem=_MAXMEM)
    return f"scrypt${_N}${_R}${_P}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, dk = stored.split("$")
        if algo != "scrypt":
            return False
        expected = bytes.fromhex(dk)
        new = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r),
                             p=int(p), dklen=len(expected), maxmem=_MAXMEM)
        return hmac.compare_digest(new, expected)
    except (ValueError, TypeError):
        return False


# Hash factice : on vérifie toujours un hash, même pour un utilisateur inconnu (anti-énumération).
DUMMY_HASH = hash_password("dummy-password-not-used")


def check_password_policy(password: str) -> None:
    problems = []
    if len(password) < config.PASSWORD_MIN_LENGTH:
        problems.append(f"{config.PASSWORD_MIN_LENGTH} caractères minimum")
    if len(password) > 128:
        problems.append("128 caractères maximum")
    if not re.search(r"[a-z]", password):
        problems.append("une minuscule")
    if not re.search(r"[A-Z]", password):
        problems.append("une majuscule")
    if not re.search(r"\d", password):
        problems.append("un chiffre")
    if not re.search(r"[^\w\s]", password):
        problems.append("un caractère spécial")
    if problems:
        raise ValidationError("Mot de passe trop faible : " + ", ".join(problems) + ".")
