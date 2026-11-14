"""Migration 11 : accélération des recherches d'impayés par élève, année et poste."""
MIGRATION_11 = """
CREATE INDEX idx_payments_arrears
    ON payments(student_id, school_year, fee_code, cancelled);
"""
