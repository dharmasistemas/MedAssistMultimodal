"""Eventos em banco descartável; nenhuma mídia/provider ou banco de usuário."""
from contextlib import closing
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
import sqlite3
import tempfile
import unittest
from uuid import UUID

from medassistmultimodal.demo.fixtures import build_demo_cases
from medassistmultimodal.domain.events import ReviewStatus, SourceKind
from medassistmultimodal.domain.session import SubjectIdentity, SubjectKind
from medassistmultimodal.infrastructure.sqlite_multimodal_schema import initialize_multimodal_schema
from medassistmultimodal.infrastructure.sqlite_session_repository import SQLiteSessionRepository
from medassistmultimodal.infrastructure.sqlite_event_repository import SQLiteEventRepository
from medassistmultimodal.infrastructure.sqlite_patient_repository import SQLitePatientRepository
from tests.unit.test_privacy import create_patient_context


def connection(path=':memory:'):
    result = sqlite3.connect(path)
    result.execute('PRAGMA foreign_keys=ON')
    initialize_multimodal_schema(result)
    return result


class SQLiteEventsTests(unittest.TestCase):
    def setUp(self):
        self.db = connection()
        self.addCleanup(self.db.close)
        self.sessions = SQLiteSessionRepository(self.db)
        self.events = SQLiteEventRepository(self.db)
        case = build_demo_cases()[0]
        self.session, self.event = case.session, case.events[0]
        SQLitePatientRepository(self.db).save(create_patient_context())
        self.sessions.save(self.session)
        self.db.commit()

    def test_roundtrip_pending_mock_and_missing(self):
        self.events.save(self.event)
        self.assertEqual(self.events.get_by_id(self.event.event_id), self.event)
        self.assertEqual(self.events.list_for_session(self.session.session_id), (self.event,))
        self.assertIsNone(self.events.get_by_id(UUID(int=99)))
        self.assertEqual(self.events.list_for_session(UUID(int=99)), ())
        self.assertTrue(self.db.in_transaction)

    def test_same_id_same_content_and_different_content(self):
        self.events.save(self.event)
        self.events.save(self.event)
        self.assertEqual(self.db.execute('SELECT count(*) FROM multimodal_events').fetchone()[0], 1)
        changes = [dict(source='other:v1'), dict(evidence_ref='sample:another'),
                   dict(processor='other:v1'), dict(is_mock=False), dict(confidence=0.5),
                   dict(timestamp=self.event.timestamp+timedelta(seconds=1)),
                   dict(review_status=ReviewStatus.REVIEWED), dict(source_kind=SourceKind.SIMULATED)]
        for values in changes:
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.events.save(replace(self.event, **values))
        self.assertEqual(self.events.get_by_id(self.event.event_id), self.event)

    def test_missing_session_and_wrong_subject_rejected(self):
        with self.assertRaises(ValueError):
            self.events.save(replace(self.event, session_id=UUID(int=99)))
        with self.assertRaises(ValueError):
            self.events.save(replace(self.event, patient_id='PAT-002'))
        self.assertEqual(self.events.list_for_session(self.session.session_id), ())

    def test_dataset_identity_provider_and_isolation(self):
        for number,dataset,participant in [(10,'illustrative:v1','A'),(11,'illustrative:v2','A'),(12,'illustrative:v1','B')]:
            subject=SubjectIdentity(kind=SubjectKind.DATASET_PARTICIPANT,
                                    dataset_id=dataset,participant_ref=participant)
            session=replace(self.session,session_id=UUID(int=number),subject=subject)
            self.sessions.save(session)
            event=replace(self.event,event_id=UUID(int=number),session_id=session.session_id,
                          subject_kind=subject.kind,patient_id=None,dataset_id=dataset,
                          participant_ref=participant,source_kind=SourceKind.DATASET)
            self.events.save(event)
            self.assertEqual(self.events.get_by_id(event.event_id),event)
            self.assertEqual(self.events.list_for_session(session.session_id),(event,))
            with self.assertRaises(ValueError):
                self.events.save(replace(event,event_id=UUID(int=number+100),participant_ref='wrong'))
        self.assertEqual(self.events.list_for_session(self.session.session_id),())

    def test_initial_review_cannot_be_forged(self):
        for status in (ReviewStatus.REVIEWED, ReviewStatus.DISMISSED):
            with self.subTest(status=status),self.assertRaises(ValueError):
                self.events.save(replace(self.event,review_status=status))
        self.assertEqual(self.events.list_for_session(self.session.session_id),())

    def test_confidence_none_and_inclusive_limits(self):
        for number,value in enumerate((None,0,1,0.5),start=20):
            event=replace(self.event,event_id=UUID(int=number),confidence=value)
            self.events.save(event)
            self.assertEqual(self.events.get_by_id(event.event_id),event)
        for value in (-0.01,1.01,float('nan'),float('inf'),True):
            with self.subTest(value=value),self.assertRaises(ValueError):
                self.events.save(replace(self.event,confidence=value))

    def test_ordering_by_timestamp_then_id(self):
        events=[replace(self.event,event_id=UUID(int=number),timestamp=self.event.timestamp+timedelta(seconds=offset))
                for number,offset in [(4,1),(3,0),(2,0)]]
        for event in events:self.events.save(event)
        self.assertEqual([e.event_id.int for e in self.events.list_for_session(self.session.session_id)],[2,3,4])

    def test_caller_rollback_preserves_committed_event(self):
        self.events.save(self.event)
        self.db.commit()
        other=replace(self.event,event_id=UUID(int=99))
        self.events.save(other)
        self.db.rollback()
        self.assertEqual(self.events.get_by_id(self.event.event_id),self.event)
        self.assertIsNone(self.events.get_by_id(other.event_id))

    def test_sql_guards_origin_missing_session_and_update(self):
        parameters=(str(UUID(int=90)),str(self.session.session_id),'dataset','fixture:v1',
                    self.event.timestamp.isoformat(),None,'sample:1','pending_review','fixture:v1',1)
        statement='INSERT INTO multimodal_events VALUES (?,?,?,?,?,?,?,?,?,?)'
        with self.assertRaises(sqlite3.IntegrityError):self.db.execute(statement,parameters)
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute(statement,(parameters[0],str(UUID(int=99)),'synthetic',*parameters[3:]))
        self.events.save(self.event)
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute("UPDATE multimodal_events SET source_kind='dataset'")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.execute('DELETE FROM multimodal_sessions')
        for field,value in [('confidence',1.1),('source',''),('is_mock',2),('processor',None)]:
            with self.subTest(field=field),self.assertRaises(sqlite3.IntegrityError):
                self.db.execute(f'UPDATE multimodal_events SET {field}=?',(value,))

    def test_corrupt_timestamp_is_not_silently_repaired(self):
        self.events.save(self.event)
        self.db.execute("UPDATE multimodal_events SET timestamp='bad-date'")
        with self.assertRaisesRegex(ValueError,'Integridade'):
            self.events.get_by_id(self.event.event_id)
        with self.assertRaisesRegex(ValueError,'Integridade'):
            self.events.list_for_session(self.session.session_id)

    def test_foreign_keys_disabled_or_version_changed_rejected(self):
        self.db.execute('PRAGMA foreign_keys=OFF')
        with self.assertRaises(ValueError):self.events.save(self.event)
        with self.assertRaises(ValueError):SQLiteEventRepository(self.db)
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('UPDATE multimodal_schema_versions SET version=2')
        self.db.commit()
        with self.assertRaises(ValueError):self.events.save(self.event)

    def test_file_reopen_preserves_event(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'events.sqlite3'
            with closing(connection(path)) as db:
                SQLitePatientRepository(db).save(create_patient_context())
                SQLiteSessionRepository(db).save(self.session)
                SQLiteEventRepository(db).save(self.event)
                db.commit()
            with closing(connection(path)) as db:
                self.assertEqual(SQLiteEventRepository(db).get_by_id(self.event.event_id),self.event)
