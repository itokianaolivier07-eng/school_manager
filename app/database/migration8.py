"""Migration 8 : coordonnées téléphoniques des responsables des élèves."""
MIGRATION_8 = """
ALTER TABLE students ADD COLUMN tutor_phone TEXT;
ALTER TABLE students ADD COLUMN father_phone TEXT;
ALTER TABLE students ADD COLUMN mother_phone TEXT;
"""
