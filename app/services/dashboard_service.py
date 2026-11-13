from app.core import school


class DashboardService:
    def __init__(self, ctx):
        self.ctx = ctx
        self.db = ctx.db

    def summary(self) -> dict:
        s = self.ctx.session
        s.require("dashboard.read")
        one = lambda sql, p=(): self.db.one(sql, p)[0]
        data = {
            "students": one("SELECT COUNT(*) FROM students WHERE status = 'active'"),
            "classes": one("SELECT COUNT(*) FROM classes"),
            "teachers": one("SELECT COUNT(*) FROM teachers"),
            "by_level": {lvl: one("SELECT COUNT(*) FROM students st JOIN classes c ON c.id = st.class_id "
                                  "WHERE st.status = 'active' AND c.level = ?", (lvl,))
                         for lvl in school.LEVELS},
            "school_year": school.current_school_year(),
        }
        if s.can("payments.read"):
            year = data["school_year"]
            data["collected_year"] = one("SELECT COALESCE(SUM(amount),0) FROM payments "
                                         "WHERE cancelled = 0 AND school_year = ?", (year,))
            data["collected_month"] = one("SELECT COALESCE(SUM(amount),0) FROM payments WHERE cancelled = 0 "
                                          "AND strftime('%Y-%m', paid_at) = strftime('%Y-%m', 'now')")
        return data
