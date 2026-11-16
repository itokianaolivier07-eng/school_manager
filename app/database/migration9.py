"""Migration 9 : professions des responsables des élèves."""
MIGRATION_9 = """
ALTER TABLE students ADD COLUMN tutor_profession TEXT
    CHECK (tutor_profession IS NULL OR length(tutor_profession) <= 100);
ALTER TABLE students ADD COLUMN father_profession TEXT
    CHECK (father_profession IS NULL OR length(father_profession) <= 100);
ALTER TABLE students ADD COLUMN mother_profession TEXT
    CHECK (mother_profession IS NULL OR length(mother_profession) <= 100);
"""
