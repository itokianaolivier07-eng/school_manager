"""Migration 10 : rémunérations horaires et historique des sorties de salaire."""
MIGRATION_10 = """
ALTER TABLE employee_salaries RENAME TO employee_salaries_legacy;
CREATE TABLE employee_salaries (
    id INTEGER PRIMARY KEY,
    employee_id INTEGER NOT NULL UNIQUE REFERENCES teachers(id) ON DELETE CASCADE,
    monthly_amount INTEGER NOT NULL DEFAULT 0 CHECK(monthly_amount >= 0),
    pay_type TEXT NOT NULL DEFAULT 'monthly' CHECK(pay_type IN ('monthly', 'hourly')),
    hourly_rate INTEGER NOT NULL DEFAULT 0 CHECK(hourly_rate >= 0),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT INTO employee_salaries (id, employee_id, monthly_amount, updated_at)
SELECT id, employee_id, monthly_amount, updated_at FROM employee_salaries_legacy;
DROP TABLE employee_salaries_legacy;

CREATE TABLE salary_disbursements (
    id INTEGER PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES teachers(id) ON DELETE RESTRICT,
    title TEXT NOT NULL,
    payout_date TEXT NOT NULL,
    school_year TEXT NOT NULL,
    hours REAL,
    hourly_rate INTEGER,
    amount INTEGER NOT NULL CHECK(amount > 0),
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK((hours IS NULL AND hourly_rate IS NULL) OR
          (hours > 0 AND hourly_rate > 0))
);
CREATE INDEX idx_salary_disbursements_date
    ON salary_disbursements(payout_date, employee_id);
CREATE INDEX idx_salary_disbursements_year
    ON salary_disbursements(school_year, employee_id);
"""
