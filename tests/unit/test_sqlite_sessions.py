"""Persistência offline em memória/arquivo temporário, sem banco do usuário."""
from dataclasses import replace
from datetime import timedelta, timezone
from pathlib import Path
import sqlite3
from contextlib import closing
import tempfile
import unittest
from uuid import UUID

from medassistmultimodal.demo.fixtures import build_demo_cases
from medassistmultimodal.domain.session import SubjectIdentity, SubjectKind
from medassistmultimodal.infrastructure.sqlite_multimodal_schema import initialize_multimodal_schema
from medassistmultimodal.infrastructure.sqlite_session_repository import SQLiteSessionRepository
from medassistmultimodal.infrastructure.sqlite_patient_repository import SQLitePatientRepository
from tests.unit.test_privacy import create_patient_context


def connect(path=':memory:'):
    connection = sqlite3.connect(path)
    connection.execute('PRAGMA foreign_keys=ON')
    return connection


class SQLiteSessionsTests(unittest.TestCase):
    def setUp(self):
        self.connection = connect()
        self.addCleanup(self.connection.close)
        initialize_multimodal_schema(self.connection)
        self.repository = SQLiteSessionRepository(self.connection)
        self.session = build_demo_cases()[0].session
        SQLitePatientRepository(self.connection).save(create_patient_context())
        self.connection.commit()

    def test_roundtrip_and_missing(self):
        self.repository.save(self.session)
        self.assertEqual(self.repository.get_by_id(self.session.session_id), self.session)
        self.assertIsNone(self.repository.get_by_id(UUID(int=99)))
        self.assertTrue(self.connection.in_transaction)

    def test_idempotence_conflicts_and_previous_content_preserved(self):
        self.repository.save(self.session)
        self.repository.save(self.session)
        self.assertEqual(self.connection.execute('SELECT count(*) FROM multimodal_sessions').fetchone()[0], 1)
        for changed in (replace(self.session, started_at=self.session.started_at+timedelta(seconds=1)),
                        replace(self.session, subject=SubjectIdentity(kind=SubjectKind.DATASET_PARTICIPANT,
                                              dataset_id='illustrative:v1', participant_ref='A'))):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                self.repository.save(changed)
        self.assertEqual(self.repository.get_by_id(self.session.session_id), self.session)

    def test_caller_rollback_preserves_committed_records(self):
        self.repository.save(self.session)
        self.connection.commit()
        other = replace(self.session, session_id=UUID(int=23))
        self.repository.save(other)
        self.connection.rollback()
        self.assertIsNone(self.repository.get_by_id(other.session_id))
        self.assertEqual(self.repository.get_by_id(self.session.session_id), self.session)

    def test_missing_patient_rejected_without_automatic_creation(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.repository.save(build_demo_cases()[1].session)
        self.assertIsNone(SQLitePatientRepository(self.connection).get_by_id('PAT-002'))

    def test_dataset_isolation_and_deterministic_order(self):
        subjects = [SubjectIdentity(kind=SubjectKind.DATASET_PARTICIPANT, dataset_id=d, participant_ref=p)
                    for d,p in [('illustrative:v1','A'),('illustrative:v2','A'),('illustrative:v1','B')]]
        for index,subject in enumerate(subjects):
            self.repository.save(replace(self.session, session_id=UUID(int=index+10), subject=subject))
        self.repository.save(replace(self.session, session_id=UUID(int=9), subject=subjects[0]))
        rows=self.repository.list_for_dataset_participant('illustrative:v1','A')
        self.assertEqual([s.session_id.int for s in rows], [9,10])
        self.assertEqual(self.repository.list_for_patient('PAT-001'), ())
        self.assertEqual(self.connection.execute('SELECT count(*) FROM synthetic_patient_contexts').fetchone()[0],1)

    def test_patient_history_and_equal_instants(self):
        for number in (3,2):
            self.repository.save(replace(self.session,session_id=UUID(int=number)))
        self.assertEqual([s.session_id.int for s in self.repository.list_for_patient('PAT-001')],[2,3])
        local=replace(self.session, started_at=self.session.started_at.astimezone(timezone(timedelta(hours=-3))))
        self.repository.save(self.session)
        self.repository.save(local)
        raw=self.connection.execute('SELECT started_at FROM multimodal_sessions WHERE session_id=?',
                                    (str(self.session.session_id),)).fetchone()[0]
        self.assertEqual(raw,'2026-10-24T12:01:00.000000+00:00')

    def test_sql_identity_guards_and_immutable_subject(self):
        for identity in [('synthetic_patient',None,None,None),
                         ('synthetic_patient','PAT-001','dataset','A'),
                         ('dataset_participant',None,None,'A'),
                         ('dataset_participant',None,'v1','')]:
            with self.subTest(identity=identity),self.assertRaises(sqlite3.IntegrityError):
                self.connection.execute('INSERT INTO multimodal_sessions VALUES (?,?,?,?,?,?)',
                                        ('bad',*identity,'date'))
        self.repository.save(self.session)
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute("UPDATE multimodal_sessions SET patient_id='PAT-002'")
        with self.assertRaises(sqlite3.IntegrityError):
            self.connection.execute("DELETE FROM synthetic_patient_contexts WHERE patient_id='PAT-001'")

    def test_reinitialization_preserves_existing_patient_and_session(self):
        self.repository.save(self.session)
        self.connection.commit()
        initialize_multimodal_schema(self.connection)
        self.assertEqual(self.repository.get_by_id(self.session.session_id),self.session)
        self.assertEqual(SQLitePatientRepository(self.connection).get_by_id('PAT-001'),create_patient_context())

    def test_schema_change_or_new_version_refused_without_repair(self):
        self.connection.execute('UPDATE multimodal_schema_versions SET version=2')
        self.connection.commit()
        with self.assertRaises(ValueError): initialize_multimodal_schema(self.connection)
        self.assertEqual(self.connection.execute('SELECT version FROM multimodal_schema_versions').fetchone()[0],2)
        with self.assertRaises(ValueError): self.repository.save(self.session)
        self.connection.execute('UPDATE multimodal_schema_versions SET version=1')
        self.connection.execute('ALTER TABLE multimodal_sessions ADD COLUMN unexpected TEXT')
        self.connection.commit()
        with self.assertRaises(ValueError): initialize_multimodal_schema(self.connection)

    def test_foreign_keys_and_active_transaction_refused(self):
        self.connection.execute('PRAGMA foreign_keys=OFF')
        with self.assertRaises(ValueError): SQLiteSessionRepository(self.connection)
        with self.assertRaises(ValueError): initialize_multimodal_schema(self.connection)
        with self.assertRaises(ValueError): self.repository.get_by_id(self.session.session_id)
        self.connection.execute('PRAGMA foreign_keys=ON')
        self.repository.save(self.session)
        with self.assertRaises(ValueError): initialize_multimodal_schema(self.connection)
        self.assertTrue(self.connection.in_transaction)
        self.connection.rollback()
        self.assertIsNone(self.repository.get_by_id(self.session.session_id))

    def test_partial_schema_and_incompatible_baseline_refused(self):
        for statement in ('CREATE TABLE multimodal_sessions (session_id TEXT)',
                          'CREATE TABLE synthetic_patient_contexts (patient_id TEXT)'):
            with closing(connect()) as connection:
                connection.execute(statement)
                with self.assertRaises(ValueError): initialize_multimodal_schema(connection)
                self.assertIsNone(connection.execute("SELECT name FROM sqlite_master WHERE name='multimodal_events'").fetchone())

    def test_invalid_persisted_data_not_silently_repaired(self):
        self.repository.save(self.session)
        self.connection.execute("UPDATE multimodal_sessions SET started_at='not-a-date'")
        with self.assertRaisesRegex(ValueError,'Integridade'): self.repository.get_by_id(self.session.session_id)

    def test_reopen_file_database(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'test.sqlite3'
            with closing(connect(path)) as connection:
                initialize_multimodal_schema(connection)
                SQLitePatientRepository(connection).save(create_patient_context())
                SQLiteSessionRepository(connection).save(self.session)
                connection.commit()
            with closing(connect(path)) as connection:
                initialize_multimodal_schema(connection)
                self.assertEqual(SQLiteSessionRepository(connection).get_by_id(self.session.session_id),self.session)

    def test_additive_initialization_preserves_baseline_patient_and_audit(self):
        from medassistmultimodal.infrastructure.sqlite_audit_repository import SQLiteAuditRepository
        with closing(connect()) as connection:
            SQLitePatientRepository(connection).initialize()
            SQLiteAuditRepository(connection).initialize()
            SQLitePatientRepository(connection).save(create_patient_context())
            connection.execute("INSERT INTO audit_records(correlation_id,patient_id,payload) VALUES (?,?,?)",
                               ('historical-reference','PAT-001','{}'))
            connection.commit()
            before = tuple(connection.execute('SELECT * FROM audit_records').fetchone())
            initialize_multimodal_schema(connection)
            self.assertEqual(tuple(connection.execute('SELECT * FROM audit_records').fetchone()), before)
            self.assertEqual(SQLitePatientRepository(connection).get_by_id('PAT-001'), create_patient_context())
