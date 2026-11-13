"""Migration 7 : salaires et pointages des employés."""
MIGRATION_7 = """
DROP TABLE grades;
DROP TABLE subjects;

CREATE TABLE employee_salaries (
    id INTEGER PRIMARY KEY,
    employee_id INTEGER NOT NULL UNIQUE REFERENCES teachers(id) ON DELETE CASCADE,
    monthly_amount INTEGER NOT NULL CHECK(monthly_amount > 0),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE employee_attendance (
    id INTEGER PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
    attendance_date TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('present', 'absent', 'late')),
    arrival_time TEXT,
    departure_time TEXT,
    comment TEXT,
    CHECK(
        (status = 'absent' AND arrival_time IS NULL AND departure_time IS NULL)
        OR
        (status IN ('present', 'late')
         AND arrival_time IS NOT NULL AND departure_time IS NOT NULL
         AND arrival_time < departure_time)
    ),
    UNIQUE(employee_id, attendance_date)
);
CREATE INDEX idx_employee_attendance_date ON employee_attendance(attendance_date, employee_id);
"""
