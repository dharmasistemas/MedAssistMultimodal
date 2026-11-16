"""Regressão dos pacientes sintéticos com SQLite em memória, sem seeds ausentes."""
import sqlite3
import unittest
from dataclasses import replace

from tests.unit.test_privacy import create_patient_context
from medassistmultimodal.infrastructure.sqlite_patient_repository import SQLitePatientRepository


class SQLitePatientRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.addCleanup(self.connection.close)
        self.repository = SQLitePatientRepository(self.connection)
        self.repository.initialize()

    def test_preserves_patient_encounters_exams_and_dates(self):
        context = create_patient_context()
        self.repository.save(context)
        self.assertEqual(self.repository.get_by_id(context.patient.patient_id), context)
        self.assertIsNone(self.repository.get_by_id("PAT-999"))

    def test_non_synthetic_patient_and_invalid_identifier_are_rejected(self):
        context = create_patient_context()
        with self.assertRaises(ValueError):
            replace(context, patient=replace(context.patient, synthetic=False))
        for value in ("", "PAT-001' OR 1=1", "../file", "PAT-0000"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.repository.get_by_id(value)

    def test_repeated_save_updates_single_patient_and_rollback_is_owned_by_caller(self):
        context = create_patient_context()
        self.repository.save(context)
        self.repository.save(context)
        self.assertEqual(self.connection.execute(
            "SELECT COUNT(*) FROM synthetic_patient_contexts").fetchone()[0], 1)
        self.connection.rollback()
        self.assertIsNone(self.repository.get_by_id(context.patient.patient_id))
