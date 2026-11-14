"""Migration 15 : journal d'audit non modifiable et traçabilité des annulations de paiement."""
MIGRATION_15 = """
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    user_id INTEGER,
    username TEXT,
    action TEXT NOT NULL,
    entity TEXT NOT NULL,
    entity_id INTEGER,
    detail TEXT
);
CREATE INDEX idx_audit_log_at ON audit_log(at);
CREATE INDEX idx_audit_log_entity ON audit_log(entity, entity_id);
CREATE TRIGGER trg_audit_log_no_update BEFORE UPDATE ON audit_log
BEGIN SELECT RAISE(ABORT, 'Le journal d audit ne peut pas etre modifie.'); END;
CREATE TRIGGER trg_audit_log_no_delete BEFORE DELETE ON audit_log
BEGIN SELECT RAISE(ABORT, 'Le journal d audit ne peut pas etre supprime.'); END;

ALTER TABLE payments ADD COLUMN cancelled_by INTEGER REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE payments ADD COLUMN cancelled_at TEXT;
"""
