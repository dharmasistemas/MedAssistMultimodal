"""Regressão da auditoria portada de PostgreSQL para SQLite real em memória."""
import json
import sqlite3
import unittest
from dataclasses import replace

from tests.unit.test_audit import create_record
from medassistmultimodal.infrastructure.sqlite_audit_repository import SQLiteAuditRepository


class SQLiteAuditRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.addCleanup(self.connection.close)
        self.repository = SQLiteAuditRepository(self.connection)
        self.repository.initialize()

    def test_saves_parameterized_record_and_redacts_nested_secrets(self):
        record = replace(create_record(), operation="Operation token=super-secret-value",
                         events=({"nested": {"detail": "Bearer super-secret-value"}},))
        identifier = self.repository.save(record)
        row = self.connection.execute(
            "SELECT audit_record_id, payload FROM audit_records"
        ).fetchone()
        self.assertEqual(identifier, row[0])
        self.assertNotIn("super-secret-value", row[1])
        self.assertEqual(json.loads(row[1])["decision"], record.decision)
        self.assertEqual(self.connection.execute(
            "SELECT COUNT(*) FROM audit_records").fetchone()[0], 1)

    def test_duplicate_is_idempotent_and_conflicting_content_is_rejected(self):
        record = create_record()
        first = self.repository.save(record)
        self.assertEqual(self.repository.save(record), first)
        with self.assertRaises(ValueError):
            self.repository.save(replace(record, operation="Different operation"))

    def test_caller_can_rollback(self):
        self.repository.save(create_record())
        self.connection.rollback()
        self.assertEqual(self.connection.execute(
            "SELECT COUNT(*) FROM audit_records").fetchone()[0], 0)
