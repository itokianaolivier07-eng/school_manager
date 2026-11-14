"""Migration 9 : professions des responsables des élèves."""
MIGRATION_9 = """
ALTER TABLE students ADD COLUMN tutor_profession TEXT;
ALTER TABLE students ADD COLUMN father_profession TEXT;
ALTER TABLE students ADD COLUMN mother_profession TEXT;
"""
