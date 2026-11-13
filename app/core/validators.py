"""Validation et nettoyage stricts des entrées (liste blanche)."""
import math
import re
from datetime import date

from app.core.exceptions import ValidationError

NAME_RE = re.compile(r"^[^\W\d_]+(?:[ '’\-][^\W\d_]+)*$", re.UNICODE)
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^\+?[0-9 .\-]{6,20}$")
CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-_]{1,19}$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9._\-]{3,50}$")
YEAR_RE = re.compile(r"^\d{4}-\d{4}$")


def text(data, key, label, *, required=True, max_len=100, pattern=None, upper=False, error=None):
    v = data.get(key)
    v = "" if v is None else str(v).strip()
    if upper:
        v = v.upper()
    if not v:
        if required:
            raise ValidationError(f"{label} est obligatoire.")
        return None
    if len(v) > max_len:
        raise ValidationError(f"{label} : {max_len} caractères maximum.")
    if any(ord(c) < 32 for c in v):
        raise ValidationError(f"{label} contient des caractères invalides.")
    if pattern and not pattern.match(v):
        raise ValidationError(error or f"{label} est invalide.")
    return v


def date_iso(data, key, label, *, required=True, min_year=1900, allow_future=False):
    raw = text(data, key, label, required=required, max_len=10)
    if raw is None:
        return None
    try:
        d = date.fromisoformat(raw)
    except ValueError:
        raise ValidationError(f"{label} : format attendu AAAA-MM-JJ.") from None
    if d.year < min_year or (not allow_future and d > date.today()):
        raise ValidationError(f"{label} est hors limites.")
    return d.isoformat()


def school_year(data, key, label="Année scolaire"):
    value = text(data, key, label, max_len=9, pattern=YEAR_RE,
                 error=f"{label} : format AAAA-AAAA.")
    start, end = (int(year) for year in value.split("-"))
    if start < 1900 or end != start + 1:
        raise ValidationError(f"{label} doit couvrir deux années consécutives.")
    return value


def choice(data, key, label, allowed, *, required=True, default=None):
    v = data.get(key)
    v = default if v in (None, "") else v
    if v is None:
        if required:
            raise ValidationError(f"{label} est obligatoire.")
        return None
    if v not in allowed:
        raise ValidationError(f"{label} : valeur non autorisée.")
    return v


def integer(data, key, label, *, required=False, minimum=None, maximum=None):
    v = data.get(key)
    if v in (None, ""):
        if required:
            raise ValidationError(f"{label} est obligatoire.")
        return None
    try:
        if isinstance(v, bool):
            raise ValueError
        if isinstance(v, float):
            if not math.isfinite(v) or not v.is_integer():
                raise ValueError
            n = int(v)
        else:
            raw = str(v).strip()
            if not re.fullmatch(r"[+-]?[0-9]+", raw):
                raise ValueError
            n = int(raw)
    except (TypeError, ValueError):
        raise ValidationError(f"{label} doit être un entier.") from None
    if (minimum is not None and n < minimum) or (maximum is not None and n > maximum):
        raise ValidationError(f"{label} est hors limites.")
    return n


def number(data, key, label, *, required=True, minimum=0.0, maximum=20.0):
    v = data.get(key)
    if v in (None, ""):
        if required:
            raise ValidationError(f"{label} est obligatoire.")
        return None
    try:
        n = float(str(v).replace(",", "."))
    except ValueError:
        raise ValidationError(f"{label} doit être un nombre.") from None
    if not (minimum <= n <= maximum) or n != n:
        raise ValidationError(f"{label} doit être comprise entre {minimum:g} et {maximum:g}.")
    return round(n, 2)
