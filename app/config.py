"""Configuration centrale de l'application."""
import os
from pathlib import Path

APP_NAME = "SchoolManager"

# Racine des données : chaque école y dispose de son propre sous-dossier isolé.
ROOT_DIR = Path(os.environ.get("SCHOOL_DATA_DIR", Path.home() / ".school_manager"))
SCHOOLS = ("ZINA", "LA BÉNÉDICTION", "LES PETITS COQUINS")  # établissements gérés
ACCOUNTS_PATH = ROOT_DIR / "accounts.db"   # comptes partagés par les trois écoles
LOG_DIR = ROOT_DIR / "logs"

# Chemins de l'école active ; réaffectés par use_school().
CURRENT_SCHOOL = SCHOOLS[0]
DATA_DIR = ROOT_DIR / "ecole_1"
DB_PATH = DATA_DIR / "school.db"
BACKUP_DIR = DATA_DIR / "backups"

PAGE_SIZE = 100                    # lignes chargées par page (pagination côté SQL)
SEARCH_DEBOUNCE_MS = 300
MAX_FAILED_LOGINS = 5
LOCKOUT_SECONDS = 300
SESSION_TIMEOUT_SECONDS = 15 * 60  # déconnexion après inactivité
PASSWORD_MIN_LENGTH = 10
BACKUP_KEEP = 10
MAX_IMPORT_BYTES = 25 * 1024 * 1024


def external_backup_dir():
    """Dossier de copie externe des sauvegardes (clé USB, autre disque, cloud synchronisé), ou None."""
    value = os.environ.get("SCHOOL_BACKUP_DIR", "").strip()
    if not value:
        try:
            value = (ROOT_DIR / "external_backup_dir.txt").read_text(encoding="utf-8").strip()
        except OSError:
            value = ""
    return Path(value) if value else None


def set_external_backup_dir(path) -> None:
    target = ROOT_DIR / "external_backup_dir.txt"
    if path:
        target.write_text(str(path), encoding="utf-8")
    else:
        target.unlink(missing_ok=True)


def use_school(index: int) -> None:
    """Active l'école d'indice donné ; ses données restent isolées des autres écoles."""
    global CURRENT_SCHOOL, DATA_DIR, DB_PATH, BACKUP_DIR
    CURRENT_SCHOOL = SCHOOLS[index]
    DATA_DIR = ROOT_DIR / f"ecole_{index + 1}"
    DB_PATH = DATA_DIR / "school.db"
    BACKUP_DIR = DATA_DIR / "backups"


def ensure_root() -> None:
    """Crée la racine des données et le dossier des journaux."""
    for d in (ROOT_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)
        os.chmod(d, 0o700)


def ensure_dirs() -> None:
    """Crée les dossiers de données de l'école active, accessibles uniquement par l'utilisateur."""
    for d in (DATA_DIR, BACKUP_DIR):
        d.mkdir(parents=True, exist_ok=True)
        os.chmod(d, 0o700)
