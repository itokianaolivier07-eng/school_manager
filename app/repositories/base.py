"""Repository générique : tout le SQL est paramétré, tri/recherche en liste blanche."""
from app.core import school

# Tables portant une année scolaire explicite (les charges sont datées, donc traitées à part).
_YEAR_TABLES = ("classes", "student_enrollments", "employee_school_years",
                "class_tuition_fees", "payments", "salary_disbursements")


def escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def used_school_years(db) -> list:
    """Toutes les années scolaires déjà utilisées dans l'application, plus l'année courante.

    Source unique des filtres « Année scolaire » : une année apparaît dès qu'une donnée
    la référence (classe, inscription, employé affecté, tarif, paiement, salaire, charge),
    et l'année courante (calculée sur l'horloge) est toujours proposée."""
    rows = db.all(" UNION ".join(f"SELECT school_year FROM {table}" for table in _YEAR_TABLES))
    years = {row["school_year"] for row in rows if row["school_year"]}
    for row in db.all("SELECT DISTINCT substr(expense_date, 1, 4) AS y, "
                      "substr(expense_date, 6, 2) AS m FROM expenses"):
        try:                                    # une charge sans année propre : déduite de sa date
            start = int(row["y"])
        except (TypeError, ValueError):
            continue
        if (row["m"] or "") < "09":             # septembre -> décembre appartiennent à l'année du début
            start -= 1
        years.add(f"{start}-{start + 1}")
    years.add(school.current_school_year())
    return sorted(years, reverse=True)


class BaseRepository:
    table = ""
    columns = ()            # colonnes écrivables
    extra_cols = ""         # ex: ", c.name AS class_name"
    joins = ""              # ex: "LEFT JOIN classes c ON c.id = t.class_id"
    search_fields = ()      # colonnes de la table "t" uniquement (préfixe LIKE 'abc%' => index utilisé)
    sort_fields = {}        # clé UI -> expression SQL (liste blanche)
    default_sort = "t.id"

    def __init__(self, db):
        self.db = db

    def _select(self) -> str:
        return f"SELECT t.*{self.extra_cols} FROM {self.table} t {self.joins}"

    def _where(self, search):
        search = (search or "").strip()
        if not search or not self.search_fields:
            return "", []
        pattern = escape_like(search[:100]) + "%"
        cond = " OR ".join(f"{f} LIKE ? ESCAPE '\\'" for f in self.search_fields)
        return f" WHERE ({cond})", [pattern] * len(self.search_fields)

    def page(self, search="", sort=None, desc=False, limit=100, offset=0):
        where, params = self._where(search)
        expr = self.sort_fields.get(sort, self.default_sort)  # jamais de valeur brute dans ORDER BY
        d = "DESC" if desc else "ASC"
        sql = f"{self._select()}{where} ORDER BY {expr} {d}, t.id {d} LIMIT ? OFFSET ?"
        return self.db.all(sql, [*params, int(limit), int(offset)])

    def count(self, search="") -> int:
        where, params = self._where(search)
        return self.db.one(
            f"SELECT COUNT(*) AS n FROM {self.table} t {self.joins}{where}", params)["n"]

    def get(self, id_):
        return self.db.one(f"{self._select()} WHERE t.id = ?", (id_,))

    def insert(self, data) -> int:
        cols = [c for c in self.columns if c in data]
        sql = f"INSERT INTO {self.table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})"
        return self.db.execute(sql, [data[c] for c in cols]).lastrowid

    def update(self, id_, data) -> int:
        cols = [c for c in self.columns if c in data]
        sets = ",".join(f"{c}=?" for c in cols)
        return self.db.execute(f"UPDATE {self.table} SET {sets} WHERE id=?",
                               [*[data[c] for c in cols], id_]).rowcount

    def delete(self, id_) -> int:
        return self.db.execute(f"DELETE FROM {self.table} WHERE id=?", (id_,)).rowcount

    def bulk_insert(self, rows, or_ignore=False) -> int:
        if not rows:
            return 0
        cols = [c for c in self.columns if c in rows[0]]
        verb = "INSERT OR IGNORE" if or_ignore else "INSERT"
        sql = f"{verb} INTO {self.table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})"
        return self.db.executemany(sql, [[r.get(c) for c in cols] for r in rows]).rowcount
