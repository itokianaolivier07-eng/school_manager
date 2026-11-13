"""Migration 3 : postes d'écolage tarifés par classe."""
MIGRATION_3 = """
CREATE TABLE class_tuition_fees (
    id INTEGER PRIMARY KEY,
    class_id INTEGER NOT NULL REFERENCES classes(id) ON DELETE RESTRICT,
    school_year TEXT NOT NULL,
    monthly_amount INTEGER NOT NULL DEFAULT 0 CHECK(monthly_amount >= 0),
    droit_amount INTEGER NOT NULL DEFAULT 0 CHECK(droit_amount >= 0),
    photocopy_amount INTEGER NOT NULL DEFAULT 0 CHECK(photocopy_amount >= 0),
    uniform_amount INTEGER NOT NULL DEFAULT 0 CHECK(uniform_amount >= 0),
    activity_1_amount INTEGER NOT NULL DEFAULT 0 CHECK(activity_1_amount >= 0),
    activity_2_amount INTEGER NOT NULL DEFAULT 0 CHECK(activity_2_amount >= 0),
    activity_3_amount INTEGER NOT NULL DEFAULT 0 CHECK(activity_3_amount >= 0),
    activity_4_amount INTEGER NOT NULL DEFAULT 0 CHECK(activity_4_amount >= 0),
    activity_5_amount INTEGER NOT NULL DEFAULT 0 CHECK(activity_5_amount >= 0),
    UNIQUE(class_id, school_year)
);
CREATE INDEX idx_class_tuition_fees_class ON class_tuition_fees(class_id, school_year);

INSERT OR IGNORE INTO class_tuition_fees
    (class_id, school_year, monthly_amount, droit_amount)
SELECT c.id, c.school_year, f.monthly_amount, f.registration_fee
FROM classes c JOIN tuition_fees f
  ON f.level = c.level AND f.school_year = c.school_year;

ALTER TABLE payments ADD COLUMN fee_code TEXT NOT NULL DEFAULT 'droit'
    CHECK(fee_code IN (
        'droit','photocopie','tenue',
        'september','october','november','december','january','february','march','april','may','june',
        'activity_1','activity_2','activity_3','activity_4','activity_5'
    ));
UPDATE payments
SET fee_code = CASE
    WHEN kind = 'registration' THEN 'droit'
    WHEN month = 9 THEN 'september'
    WHEN month = 10 THEN 'october'
    WHEN month = 11 THEN 'november'
    WHEN month = 12 THEN 'december'
    WHEN month = 1 THEN 'january'
    WHEN month = 2 THEN 'february'
    WHEN month = 3 THEN 'march'
    WHEN month = 4 THEN 'april'
    WHEN month = 5 THEN 'may'
    WHEN month = 6 THEN 'june'
    ELSE fee_code
END;

CREATE TRIGGER trg_payments_fee_code_immutable BEFORE UPDATE ON payments
WHEN NEW.fee_code IS NOT OLD.fee_code
BEGIN SELECT RAISE(ABORT, 'Paiement non modifiable.'); END;
"""
