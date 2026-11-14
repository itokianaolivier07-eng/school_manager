"""Migration 14 : charges d'exploitation saisies (loyer, électricité, eau, autres)."""
MIGRATION_14 = """
CREATE TABLE expenses (
    id INTEGER PRIMARY KEY,
    category TEXT NOT NULL CHECK(category IN ('loyer','electricite','eau','autre')),
    label TEXT NOT NULL DEFAULT '',
    amount INTEGER NOT NULL CHECK(amount > 0),
    expense_date TEXT NOT NULL,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_expenses_date ON expenses(expense_date);
"""
