"""Règles de facturation scolaire et année scolaire septembre -> juin."""
from datetime import date

SCHOOL_MONTHS = (9, 10, 11, 12, 1, 2, 3, 4, 5, 6)
MONTH_NAMES = {1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril", 5: "Mai", 6: "Juin", 7: "Juillet",
               8: "Août", 9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"}
METHODS = {"cash": "Espèces", "mobile_money": "Mobile Money", "bank": "Banque / virement"}
KINDS = {"registration": "Inscription", "monthly": "Écolage"}
FIXED_FEE_ITEMS = {
    "droit": "Droit",
    "photocopie": "Photocopie",
    "tenue": "Tenue",
    "activity_1": "Activité 1",
    "activity_2": "Activité 2",
    "activity_3": "Activité 3",
    "activity_4": "Activité 4",
    "activity_5": "Activité 5",
}
CORE_FEE_CODES = ("droit", "photocopie", "tenue")
ACTIVITY_FEE_CODES = (
    "activity_1", "activity_2", "activity_3", "activity_4", "activity_5",
)
MONTH_FEE_CODES = {month: MONTH_NAMES[month].lower() for month in SCHOOL_MONTHS}
MONTHS_BY_FEE_CODE = {code: month for month, code in MONTH_FEE_CODES.items()}
FEE_ITEM_LABELS = {
    **FIXED_FEE_ITEMS,
    **{code: MONTH_NAMES[month] for month, code in MONTH_FEE_CODES.items()},
}
FEE_ITEM_CODES = CORE_FEE_CODES + tuple(MONTHS_BY_FEE_CODE) + ACTIVITY_FEE_CODES
FEE_AMOUNT_FIELDS = {
    "droit": "droit_amount",
    "photocopie": "photocopy_amount",
    "tenue": "uniform_amount",
    "activity_1": "activity_1_amount",
    "activity_2": "activity_2_amount",
    "activity_3": "activity_3_amount",
    "activity_4": "activity_4_amount",
    "activity_5": "activity_5_amount",
}
MAX_AMOUNT = 10_000_000
MIN_AGE, MAX_AGE = 8, 19
DEFAULT_CAPACITY = 45


def current_school_year(today=None) -> str:
    today = today or date.today()
    start = today.year if today.month >= 9 else today.year - 1
    return f"{start}-{start + 1}"


def months_elapsed(today=None) -> int:
    """Nombre de mois d'écolage échus à cette date (septembre = 1 ... juin = 10)."""
    m = (today or date.today()).month
    if m in SCHOOL_MONTHS:
        return SCHOOL_MONTHS.index(m) + 1
    return 10 if m in (7, 8) else 0


def net_monthly(amount: int, discount: int) -> int:
    return amount * (100 - discount) // 100


def fmt_ar(n) -> str:
    return f"{int(n):,}".replace(",", " ") + " Ar"


def mention(avg):
    if avg is None:
        return ""
    return ("Très bien" if avg >= 16 else "Bien" if avg >= 14 else "Assez bien" if avg >= 12
            else "Passable" if avg >= 10 else "Insuffisant")
