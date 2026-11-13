"""Migration 2 : niveaux du collège, écolages et paiements."""
MIGRATION_2 = """
-- Les anciennes coordonnées sont conservées en base, mais retirées de l'interface.
ALTER TABLE students ADD COLUMN guardian_name TEXT;
ALTER TABLE students ADD COLUMN tuition_discount INTEGER NOT NULL DEFAULT 0
    CHECK(tuition_discount BETWEEN 0 AND 100);
ALTER TABLE classes ADD COLUMN capacity INTEGER NOT NULL DEFAULT 45 CHECK(capacity BETWEEN 1 AND 80);

CREATE TABLE tuition_fees (
    id INTEGER PRIMARY KEY,
    level TEXT NOT NULL CHECK(level IN ('6e','5e','4e','3e')),
    school_year TEXT NOT NULL,
    monthly_amount INTEGER NOT NULL CHECK(monthly_amount >= 0),
    registration_fee INTEGER NOT NULL DEFAULT 0 CHECK(registration_fee >= 0),
    UNIQUE(level, school_year)
);

CREATE TABLE payments (
    id INTEGER PRIMARY KEY,
    receipt_no TEXT UNIQUE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE RESTRICT,
    school_year TEXT NOT NULL,
    kind TEXT NOT NULL CHECK(kind IN ('registration','monthly')),
    month INTEGER CHECK(month BETWEEN 1 AND 12),
    amount INTEGER NOT NULL CHECK(amount > 0),
    method TEXT NOT NULL CHECK(method IN ('cash','mobile_money','bank')),
    reference TEXT,
    paid_at TEXT NOT NULL DEFAULT (date('now')),
    received_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    cancelled INTEGER NOT NULL DEFAULT 0 CHECK(cancelled IN (0,1)),
    cancel_reason TEXT,
    CHECK((kind = 'registration' AND month IS NULL) OR (kind = 'monthly' AND month IS NOT NULL))
);
CREATE INDEX idx_payments_student ON payments(student_id, school_year);
CREATE INDEX idx_payments_date ON payments(paid_at);
-- Intégrité comptable : un paiement ne se supprime ni ne se modifie, il s'annule.
CREATE TRIGGER trg_payments_no_delete BEFORE DELETE ON payments
BEGIN SELECT RAISE(ABORT, 'Un paiement ne peut pas etre supprime : annulez-le.'); END;
CREATE TRIGGER trg_payments_immutable BEFORE UPDATE ON payments
WHEN NEW.student_id IS NOT OLD.student_id
  OR NEW.school_year IS NOT OLD.school_year
  OR NEW.kind IS NOT OLD.kind
  OR NEW.month IS NOT OLD.month
  OR NEW.amount IS NOT OLD.amount
  OR NEW.method IS NOT OLD.method
  OR NEW.reference IS NOT OLD.reference
  OR NEW.paid_at IS NOT OLD.paid_at
  OR NEW.received_by IS NOT OLD.received_by
  OR (OLD.receipt_no IS NOT NULL AND NEW.receipt_no IS NOT OLD.receipt_no)
  OR (NEW.cancelled = OLD.cancelled AND NEW.cancel_reason IS NOT OLD.cancel_reason)
  OR (OLD.cancelled = 1 AND NEW.cancelled <> 1)
  OR (NEW.cancelled = 1 AND
      (OLD.cancelled <> 0 OR length(trim(COALESCE(NEW.cancel_reason, ''))) < 3))
BEGIN SELECT RAISE(ABORT, 'Paiement non modifiable.'); END;
"""
