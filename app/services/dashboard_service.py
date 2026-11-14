from datetime import date

from app.core import school
from app.repositories.base import used_school_years


class DashboardService:
    def __init__(self, ctx):
        self.ctx = ctx
        self.db = ctx.db

    def summary(self) -> dict:
        s = self.ctx.session
        s.require("dashboard.read")
        one = lambda sql, p=(): self.db.one(sql, p)[0]
        current_year = school.current_school_year()
        data = {
            "students": one("SELECT COUNT(*) FROM students s JOIN student_enrollments e "
                            "ON e.student_id = s.id WHERE s.status = 'active' AND e.school_year = ?",
                            (current_year,)),
            "classes": one("SELECT COUNT(*) FROM classes WHERE school_year = ?", (current_year,)),
            "employees": one("SELECT COUNT(*) FROM employee_school_years WHERE school_year = ?",
                             (current_year,)),
            "school_year": current_year,
        }
        if s.can("payments.read"):
            year = data["school_year"]
            data["collected_year"] = one("SELECT COALESCE(SUM(amount),0) FROM payments "
                                         "WHERE cancelled = 0 AND school_year = ?", (year,))
            data["collected_month"] = one("SELECT COALESCE(SUM(amount),0) FROM payments WHERE cancelled = 0 "
                                          "AND strftime('%Y-%m', paid_at) = strftime('%Y-%m', 'now', 'localtime')")
        if s.can("attendance.read"):
            data["present_today"] = one(
                "SELECT COUNT(*) FROM employee_attendance "
                "WHERE attendance_date = date('now', 'localtime') AND status IN ('present','late')")
        if s.can("salaries.read"):
            data["salary_total"] = one("SELECT COALESCE(SUM(monthly_amount),0) FROM employee_salaries")
        return data

    # --- Suivi des bénéfices (recettes - salaires/avances - charges) ---
    def finance_available(self) -> bool:
        s = self.ctx.session
        return (s.can("dashboard.read") and s.can("payments.read")
                and s.can("salaries.read") and s.can("expenses.read"))

    def finance_year_options(self) -> list:
        self.ctx.session.require("dashboard.read")
        return used_school_years(self.db)

    def finance_series(self, school_year=None, today=None):
        """Bénéfice mois par mois de l'année scolaire (septembre -> juin).

        bénéfice = encaissements du mois - (salaires/avances + loyer + eau/électricité
        + autres charges du mois)."""
        s = self.ctx.session
        s.require("dashboard.read")
        if not self.finance_available():
            return None
        year = school.current_school_year(today) if school_year is None else school_year
        start_year = int(str(year).split("-")[0])
        months = []
        for month_year, month in (*school.school_year_months(year),
                                  (start_year + 1, 7), (start_year + 1, 8)):
            months.append({
                "year": month_year, "month": month,
                "ym": f"{month_year:04d}-{month:02d}",
                "label": school.MONTH_NAMES[month],
                "short_label": school.MONTH_ABBR[month],
                "collected": 0, "salaries": 0, "loyer": 0, "utilities": 0, "other": 0,
                "expenses": 0, "spending": 0, "profit": 0,
            })
        by_month = {m["ym"]: m for m in months}
        window = (f"{start_year}-09-01", f"{start_year + 1}-08-31")

        for row in self.db.all(
                "SELECT strftime('%Y-%m', paid_at) AS ym, SUM(amount) AS total FROM payments "
                "WHERE cancelled = 0 AND paid_at BETWEEN ? AND ? GROUP BY ym", window):
            if row["ym"] in by_month:
                by_month[row["ym"]]["collected"] = row["total"] or 0

        for row in self.db.all(
                "SELECT strftime('%Y-%m', payout_date) AS ym, SUM(amount) AS total "
                "FROM salary_disbursements WHERE payout_date BETWEEN ? AND ? GROUP BY ym", window):
            if row["ym"] in by_month:
                by_month[row["ym"]]["salaries"] = row["total"] or 0

        for row in self.db.all(
                "SELECT strftime('%Y-%m', expense_date) AS ym, category, SUM(amount) AS total "
                "FROM expenses WHERE expense_date BETWEEN ? AND ? GROUP BY ym, category",
                window):
            month_row = by_month.get(row["ym"])
            if month_row is None:
                continue
            total = row["total"] or 0
            if row["category"] == "loyer":
                month_row["loyer"] += total
            elif row["category"] in ("electricite", "eau"):
                month_row["utilities"] += total
            else:
                month_row["other"] += total

        for month_row in months:
            month_row["expenses"] = month_row["loyer"] + month_row["utilities"] + month_row["other"]
            month_row["spending"] = month_row["salaries"] + month_row["expenses"]
            month_row["profit"] = month_row["collected"] - month_row["spending"]

        totals = {key: sum(m[key] for m in months)
                  for key in ("collected", "salaries", "loyer", "utilities", "other",
                              "expenses", "spending", "profit")}
        return {"school_year": year, "months": months, "totals": totals,
                "default_index": self._default_index(months, today)}

    @staticmethod
    def _default_index(months, today=None):
        today = today or date.today()
        current = f"{today.year:04d}-{today.month:02d}"
        last_month = len(months) - 1
        for index, month_row in enumerate(months):
            if month_row["ym"] == current:
                return index
            if month_row["ym"] > current:
                return max(0, index - 1) if index else 0
        return last_month
