"""Configuration centrale de l'application."""
import os
from pathlib import Path

APP_NAME = "SchoolManager"
DATA_DIR = Path(os.environ.get("SCHOOL_DATA_DIR", Path.home() / ".school_manager"))
DB_PATH = DATA_DIR / "school.db"
BACKUP_DIR = DATA_DIR / "backups"
LOG_DIR = DATA_DIR / "logs"

PAGE_SIZE = 100                    # lignes chargées par page (pagination côté SQL)
SEARCH_DEBOUNCE_MS = 300
MAX_FAILED_LOGINS = 5
LOCKOUT_SECONDS = 300
SESSION_TIMEOUT_SECONDS = 15 * 60  # déconnexion après inactivité
PASSWORD_MIN_LENGTH = 10
BACKUP_KEEP = 10
MAX_IMPORT_BYTES = 25 * 1024 * 1024


def ensure_dirs() -> None:
    """Crée les dossiers de données, accessibles uniquement par l'utilisateur."""
    for d in (DATA_DIR, BACKUP_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)
        os.chmod(d, 0o700)
