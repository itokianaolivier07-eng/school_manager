"""Service CRUD générique : permission -> validation -> transaction."""
import math
import sqlite3
from dataclasses import dataclass, field

from app import config
from app.core.exceptions import DuplicateError, NotFoundError, ValidationError


@dataclass
class Page:
    rows: list = field(default_factory=list)
    total: int = 0
    page: int = 0
    size: int = config.PAGE_SIZE

    @property
    def pages(self) -> int:
        return max(1, math.ceil(self.total / self.size))


def translate_integrity(e: sqlite3.IntegrityError):
    msg = str(e)
    if "UNIQUE" in msg:
        col = msg.rsplit(".", 1)[-1] if "." in msg else "valeur"
        return DuplicateError(f"Cette valeur existe déjà ({col}).")
    if "FOREIGN KEY" in msg:
        return ValidationError("Référence invalide ou élément encore utilisé.")
    return ValidationError("Données refusées par la base.")


class CrudService:
    entity = ""
    repo_cls = None
    read_perm = write_perm = delete_perm = ""
    default_desc = False

    def __init__(self, ctx):
        self.ctx = ctx
        self.db = ctx.db
        self.repo = self.repo_cls(ctx.db)

    # --- à surcharger ---
    def validate(self, data) -> dict:
        raise NotImplementedError

    def prepare(self, clean) -> dict:
        return clean

    # --- API ---
    @property
    def user(self):
        return self.ctx.session.user

    def page(self, search="", sort=None, desc=None, page=0, size=config.PAGE_SIZE) -> Page:
        self.ctx.session.require(self.read_perm)
        page = max(0, int(page))
        desc = self.default_desc if desc is None else desc
        rows = self.repo.page(search, sort, desc, size, page * size)
        return Page(rows, self.repo.count(search), page, size)

    def get(self, id_):
        self.ctx.session.require(self.read_perm)
        row = self.repo.get(id_)
        if row is None:
            raise NotFoundError("Élément introuvable.")
        return dict(row)

    def create(self, data) -> int:
        self.ctx.session.require(self.write_perm)
        clean = self.validate(data)
        with self.db.transaction():
            try:
                new_id = self.repo.insert(self.prepare(dict(clean)))
            except sqlite3.IntegrityError as e:
                raise translate_integrity(e) from e
        return new_id

    def update(self, id_, data) -> None:
        self.ctx.session.require(self.write_perm)
        clean = self.validate(data)
        with self.db.transaction():
            try:
                changed = self.repo.update(id_, self.prepare(dict(clean)))
            except sqlite3.IntegrityError as e:
                raise translate_integrity(e) from e
            if not changed:
                raise NotFoundError("Élément introuvable.")

    def delete(self, id_) -> None:
        self.ctx.session.require(self.delete_perm)
        with self.db.transaction():
            try:
                changed = self.repo.delete(id_)
            except sqlite3.IntegrityError as e:
                raise translate_integrity(e) from e
            if not changed:
                raise NotFoundError("Élément introuvable.")
