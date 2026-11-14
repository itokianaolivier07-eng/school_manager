"""Migration 13 : suppression du journal d'audit."""
MIGRATION_13 = """
DROP TABLE IF EXISTS audit_log;
"""
