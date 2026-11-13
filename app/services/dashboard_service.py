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
            "employees": one("SELECT COUNT(*) FROM teachers"),
            "school_year": school.current_school_year(),
        }
        if s.can("payments.read"):
            year = data["school_year"]
            data["collected_year"] = one("SELECT COALESCE(SUM(amount),0) FROM payments "
                                         "WHERE cancelled = 0 AND school_year = ?", (year,))
            data["collected_month"] = one("SELECT COALESCE(SUM(amount),0) FROM payments WHERE cancelled = 0 "
                                          "AND strftime('%Y-%m', paid_at) = strftime('%Y-%m', 'now')")
        if s.can("attendance.read"):
            data["present_today"] = one(
                "SELECT COUNT(*) FROM employee_attendance "
                "WHERE attendance_date = date('now') AND status IN ('present','late')")
        if s.can("salaries.read"):
            data["salary_total"] = one("SELECT COALESCE(SUM(monthly_amount),0) FROM employee_salaries")
        return data
