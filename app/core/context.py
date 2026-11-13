from dataclasses import dataclass

from app.core.session import Session
from app.database.connection import Database


@dataclass
class AppContext:
    db: Database
    session: Session
