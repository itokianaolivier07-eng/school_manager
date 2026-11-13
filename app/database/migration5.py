"""Migration 5 : informations personnelles et poste des enseignants."""
MIGRATION_5 = """
ALTER TABLE teachers ADD COLUMN gender TEXT CHECK(gender IN ('M','F'));
ALTER TABLE teachers ADD COLUMN birth_date TEXT;
ALTER TABLE teachers ADD COLUMN birth_place TEXT;
ALTER TABLE teachers ADD COLUMN address TEXT;
ALTER TABLE teachers ADD COLUMN position TEXT;
UPDATE teachers SET position = speciality
WHERE position IS NULL AND speciality IS NOT NULL;
"""
