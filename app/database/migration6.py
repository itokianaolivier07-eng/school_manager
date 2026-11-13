"""Migration 6 : rattachement des tarifs aux classes et retrait du niveau."""
MIGRATION_6 = """
DROP TABLE tuition_fees;
ALTER TABLE classes DROP COLUMN level;
"""
