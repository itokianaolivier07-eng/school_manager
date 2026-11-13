"""Migration 4 : niveaux de la maternelle au collège et informations des tuteurs."""
MIGRATION_4 = """
ALTER TABLE students ADD COLUMN tutor_name TEXT;
ALTER TABLE students ADD COLUMN father_name TEXT;
ALTER TABLE students ADD COLUMN mother_name TEXT;
UPDATE students SET tutor_name = guardian_name
WHERE tutor_name IS NULL AND guardian_name IS NOT NULL;

UPDATE classes
SET level = CASE level
    WHEN '6e' THEN '6è'
    WHEN '5e' THEN '5è'
    WHEN '4e' THEN '4è'
    WHEN '3e' THEN '3è'
    ELSE level
END
WHERE level IN ('6e', '5e', '4e', '3e');
"""
