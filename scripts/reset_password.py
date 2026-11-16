"""Mot de passe oublié : python -m scripts.reset_password IDENTIFIANT
Exige un accès physique au poste (même niveau de confiance que l'accès au fichier de comptes)."""
import getpass
import sys

from app import config
from app.core import security
from app.core.exceptions import ValidationError
from app.database.accounts import migrate_accounts
from app.database.connection import Database


def main(argv) -> int:
    if len(argv) != 2:
        print("Usage : python -m scripts.reset_password IDENTIFIANT")
        return 2
    config.ensure_root()
    db = Database(config.ACCOUNTS_PATH)
    try:
        migrate_accounts(db)
        row = db.one("SELECT id FROM users WHERE username = ?", (argv[1],))
        if row is None:
            print("Compte introuvable.")
            return 1
        password = getpass.getpass("Nouveau mot de passe : ")
        if password != getpass.getpass("Confirmer : "):
            print("Les mots de passe diffèrent.")
            return 1
        try:
            security.check_password_policy(password)
        except ValidationError as exc:
            print(exc)
            return 1
        with db.transaction():
            db.execute("UPDATE users SET password_hash=?, must_change_password=1, failed_attempts=0, "
                       "locked_until=NULL, is_active=1 WHERE id=?",
                       (security.hash_password(password), row["id"]))
        print("Mot de passe réinitialisé ; il devra être changé à la prochaine connexion.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
