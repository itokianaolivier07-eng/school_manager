"""Notes : saisie par classe/matière/trimestre, moyennes pondérées et classement."""
from app.core import validators as V
from app.core.exceptions import ValidationError
from app.repositories.repos import AuditRepository


class GradeService:
    def __init__(self, ctx):
        self.ctx = ctx
        self.db = ctx.db
        self.audit = AuditRepository(ctx.db)

    @staticmethod
    def _term(term):
        return V.integer({"t": term}, "t", "Trimestre", required=True, minimum=1, maximum=3)

    def sheet(self, class_id, subject_id, term):
        self.ctx.session.require("grades.read")
        return self.db.all(
            "SELECT s.id AS student_id, s.matricule, s.last_name, s.first_name, g.value, g.comment "
            "FROM students s LEFT JOIN grades g ON g.student_id = s.id AND g.subject_id = ? AND g.term = ? "
            "WHERE s.class_id = ? AND s.status = 'active' ORDER BY s.last_name, s.first_name, s.id",
            (int(subject_id), self._term(term), int(class_id)))

    def save_sheet(self, class_id, subject_id, term, entries):
        """entries: [(student_id, valeur|None, commentaire|None)] ; valeur None => note supprimée."""
        user = self.ctx.session.require("grades.write")
        term = self._term(term)
        valid_ids = {r["id"] for r in self.db.all("SELECT id FROM students WHERE class_id = ?",
                                                  (int(class_id),))}
        rows, deletes = [], []
        for sid, value, comment in entries:
            if sid not in valid_ids:
                raise ValidationError("Élève hors de la classe sélectionnée.")
            comment = V.text({"c": comment}, "c", "Commentaire", required=False, max_len=200)
            if value in (None, ""):
                deletes.append((sid, int(subject_id), term))
            else:
                rows.append((sid, int(subject_id), term, V.number({"v": value}, "v", "Note"),
                             comment, user.id))
        with self.db.transaction():
            self.db.executemany(
                "INSERT INTO grades(student_id, subject_id, term, value, comment, graded_by) "
                "VALUES (?,?,?,?,?,?) ON CONFLICT(student_id, subject_id, term) DO UPDATE SET "
                "value=excluded.value, comment=excluded.comment, graded_by=excluded.graded_by, "
                "graded_at=datetime('now')", rows)
            self.db.executemany(
                "DELETE FROM grades WHERE student_id=? AND subject_id=? AND term=?", deletes)
            self.audit.log(user, "save_grades", "grades", int(subject_id),
                           f"classe={class_id} trimestre={term} saisies={len(rows)} supprimées={len(deletes)}")
        return len(rows)

    def student_report(self, student_id):
        self.ctx.session.require("grades.read")
        return self.db.all(
            "SELECT g.term, ROUND(SUM(g.value * s.coefficient) / SUM(s.coefficient), 2) AS average "
            "FROM grades g JOIN subjects s ON s.id = g.subject_id WHERE g.student_id = ? "
            "GROUP BY g.term ORDER BY g.term", (int(student_id),))

    def ranking(self, class_id, term):
        self.ctx.session.require("grades.read")
        return self.db.all(
            "SELECT * FROM (SELECT st.id, st.matricule, st.last_name, st.first_name, "
            "ROUND(SUM(g.value * sj.coefficient) / SUM(sj.coefficient), 2) AS average, "
            "RANK() OVER (ORDER BY SUM(g.value * sj.coefficient) / SUM(sj.coefficient) DESC) AS rank "
            "FROM students st JOIN grades g ON g.student_id = st.id AND g.term = ? "
            "JOIN subjects sj ON sj.id = g.subject_id WHERE st.class_id = ? GROUP BY st.id) "
            "ORDER BY rank, last_name", (self._term(term), int(class_id)))
