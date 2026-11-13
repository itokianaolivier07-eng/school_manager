"""Règles propres à l'école (collège malgache : 6e à 3e, année scolaire octobre -> juin)."""
from datetime import date

LEVELS = ("6e", "5e", "4e", "3e")
SCHOOL_MONTHS = (10, 11, 12, 1, 2, 3, 4, 5, 6)
MONTH_NAMES = {1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril", 5: "Mai", 6: "Juin", 7: "Juillet",
               8: "Août", 9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"}
METHODS = {"cash": "Espèces", "mobile_money": "Mobile Money", "bank": "Banque / virement"}
KINDS = {"registration": "Inscription", "monthly": "Écolage"}
MAX_AMOUNT = 10_000_000
MIN_AGE, MAX_AGE = 8, 19
DEFAULT_CAPACITY = 45


def current_school_year(today=None) -> str:
    today = today or date.today()
    start = today.year if today.month >= 10 else today.year - 1
    return f"{start}-{start + 1}"


def months_elapsed(today=None) -> int:
    """Nombre de mois d'écolage échus à cette date (octobre = 1 ... juin = 9)."""
    m = (today or date.today()).month
    if m in SCHOOL_MONTHS:
        return SCHOOL_MONTHS.index(m) + 1
    return 9 if m in (7, 8, 9) else 0


def net_monthly(amount: int, discount: int) -> int:
    return amount * (100 - discount) // 100


def fmt_ar(n) -> str:
    return f"{int(n):,}".replace(",", " ") + " Ar"


def mention(avg):
    if avg is None:
        return ""
    return ("Très bien" if avg >= 16 else "Bien" if avg >= 14 else "Assez bien" if avg >= 12
            else "Passable" if avg >= 10 else "Insuffisant")
