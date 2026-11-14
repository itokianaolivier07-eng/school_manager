from dataclasses import dataclass

from app.core.session import Session
from app.database.connection import Database


@dataclass
class AppContext:
    db: Database          # base de l'école active
    session: Session
    accounts: Database    # comptes partagés par les trois écoles
