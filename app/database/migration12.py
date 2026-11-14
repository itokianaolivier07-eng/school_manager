"""Migration 12 : historique annuel des inscriptions et affectations."""
MIGRATION_12 = """
CREATE TABLE classes_new (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL COLLATE NOCASE,
    school_year TEXT NOT NULL,
    main_teacher_id INTEGER REFERENCES teachers(id) ON DELETE SET NULL,
    capacity INTEGER NOT NULL DEFAULT 45 CHECK(capacity BETWEEN 1 AND 80),
    UNIQUE(name, school_year)
);
INSERT INTO classes_new (id, name, school_year, main_teacher_id, capacity)
SELECT id, name, school_year, main_teacher_id, capacity FROM classes;
DROP TABLE classes;
ALTER TABLE classes_new RENAME TO classes;
CREATE INDEX idx_classes_year ON classes(school_year, name);

CREATE TABLE student_enrollments (
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    school_year TEXT NOT NULL,
    class_id INTEGER REFERENCES classes(id) ON DELETE RESTRICT,
    PRIMARY KEY(student_id, school_year)
);
CREATE INDEX idx_student_enrollments_year_class
    ON student_enrollments(school_year, class_id, student_id);
INSERT INTO student_enrollments (student_id, school_year, class_id)
SELECT s.id, c.school_year, s.class_id
FROM students s JOIN classes c ON c.id = s.class_id;
INSERT INTO student_enrollments (student_id, school_year, class_id)
SELECT id,
       CASE WHEN strftime('%m', 'now') >= '09'
            THEN strftime('%Y', 'now') || '-' || (CAST(strftime('%Y', 'now') AS INTEGER) + 1)
            ELSE (CAST(strftime('%Y', 'now') AS INTEGER) - 1) || '-' || strftime('%Y', 'now')
       END,
       NULL
FROM students WHERE class_id IS NULL;

CREATE TABLE employee_school_years (
    employee_id INTEGER NOT NULL REFERENCES teachers(id) ON DELETE CASCADE,
    school_year TEXT NOT NULL,
    PRIMARY KEY(employee_id, school_year)
);
CREATE INDEX idx_employee_school_years_year
    ON employee_school_years(school_year, employee_id);
INSERT INTO employee_school_years (employee_id, school_year)
SELECT t.id, y.school_year
FROM teachers t CROSS JOIN (SELECT DISTINCT school_year FROM classes) y
WHERE (t.hire_date IS NOT NULL
       AND date(t.hire_date) <= date(substr(y.school_year, 6, 4) || '-08-31'))
   OR (t.hire_date IS NULL
       AND y.school_year=(SELECT MAX(school_year) FROM classes));

CREATE TRIGGER trg_class_year_matches_enrollments
BEFORE UPDATE OF school_year ON classes
WHEN EXISTS (
    SELECT 1 FROM student_enrollments
    WHERE class_id=OLD.id AND school_year IS NOT NEW.school_year
)
BEGIN SELECT RAISE(ABORT, 'Une classe inscrite ne peut pas changer d’année scolaire.'); END;

CREATE TRIGGER trg_student_enrollment_class_year_insert
BEFORE INSERT ON student_enrollments
WHEN (SELECT school_year FROM classes WHERE id = NEW.class_id) IS NOT NEW.school_year
 AND NEW.class_id IS NOT NULL
BEGIN SELECT RAISE(ABORT, 'La classe doit appartenir à la même année scolaire.'); END;
CREATE TRIGGER trg_student_enrollment_class_year_update
BEFORE UPDATE OF class_id, school_year ON student_enrollments
WHEN (SELECT school_year FROM classes WHERE id = NEW.class_id) IS NOT NEW.school_year
 AND NEW.class_id IS NOT NULL
BEGIN SELECT RAISE(ABORT, 'La classe doit appartenir à la même année scolaire.'); END;
"""
