"""Atomicidade e repetição com SQLite real em memória/arquivo temporário."""
from contextlib import closing
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from uuid import UUID

from medassistmultimodal.application.register_multimodal_session import RegisterMultimodalSession
from medassistmultimodal.demo.fixtures import build_demo_cases
from medassistmultimodal.domain.events import ReviewStatus
from medassistmultimodal.infrastructure.sqlite_multimodal_schema import initialize_multimodal_schema
from medassistmultimodal.infrastructure.sqlite_multimodal_unit_of_work import SQLiteMultimodalUnitOfWork
from medassistmultimodal.infrastructure.sqlite_patient_repository import SQLitePatientRepository
from tests.unit.test_privacy import create_patient_context


def connect(path=':memory:'):
    db=sqlite3.connect(path)
    db.execute('PRAGMA foreign_keys=ON')
    initialize_multimodal_schema(db)
    return db


class RegisterMultimodalSessionTests(unittest.TestCase):
    def setUp(self):
        self.db=connect()
        self.addCleanup(self.db.close)
        SQLitePatientRepository(self.db).save(create_patient_context())
        self.db.commit()
        self.uow=SQLiteMultimodalUnitOfWork(self.db)
        self.use_case=RegisterMultimodalSession(self.uow)
        case=build_demo_cases()[0]
        self.session,self.event=case.session,case.events[0]
        self.correlation=UUID(int=50)

    def counts(self):
        return tuple(self.db.execute('SELECT count(*) FROM '+table).fetchone()[0]
                     for table in ('multimodal_sessions','multimodal_events','audit_records'))

    def execute(self,events=None,correlation=None,session=None):
        return self.use_case.execute(session or self.session,
            (self.event,) if events is None else events,
            correlation_id=correlation or self.correlation)

    def test_success_commits_session_events_and_audit(self):
        audit_id=self.execute()
        self.assertEqual(self.counts(),(1,1,1))
        self.assertFalse(self.db.in_transaction)
        payload=json.loads(self.db.execute('SELECT payload FROM audit_records WHERE audit_record_id=?',
                                          (audit_id,)).fetchone()[0])
        self.assertEqual(payload['events'][0]['event_id'],str(self.event.event_id))
        self.assertEqual(payload['sources'][0]['session_id'],str(self.session.session_id))
        self.assertTrue(payload['requires_human_validation'])
        self.assertEqual(payload['decision'],'completed')

    def test_failure_on_second_event_rolls_back_first_and_session(self):
        second=replace(self.event,event_id=UUID(int=(1<<128)-1),review_status=ReviewStatus.REVIEWED)
        with self.assertRaises(ValueError):self.execute((self.event,second))
        self.assertEqual(self.counts(),(0,0,0))
        self.assertFalse(self.db.in_transaction)

    def test_audit_failure_rolls_back_data(self):
        with patch.object(self.uow.audit,'save',side_effect=sqlite3.OperationalError('simulated write failure')):
            with self.assertRaises(sqlite3.OperationalError):self.execute()
        self.assertEqual(self.counts(),(0,0,0))
        self.execute()
        self.assertEqual(self.counts(),(1,1,1))

    def test_same_operation_repeat_is_idempotent_even_with_reordered_events(self):
        other=replace(self.event,event_id=UUID(int=51))
        audit_id=self.execute((self.event,other))
        self.assertEqual(self.execute((other,self.event)),audit_id)
        self.assertEqual(self.counts(),(1,2,1))

    def test_correlation_conflict_rolls_back_new_event_preserving_previous_data(self):
        self.execute()
        before=self.db.execute('SELECT payload FROM audit_records').fetchone()[0]
        other=replace(self.event,event_id=UUID(int=51))
        with self.assertRaises(ValueError):self.execute((self.event,other))
        self.assertEqual(self.counts(),(1,1,1))
        self.assertEqual(self.db.execute('SELECT payload FROM audit_records').fetchone()[0],before)
        self.assertIsNone(self.uow.events.get_by_id(other.event_id))

    def test_event_conflict_preserves_previously_committed_records(self):
        self.execute()
        with self.assertRaises(ValueError):
            self.execute((replace(self.event,evidence_ref='changed'),),correlation=UUID(int=52))
        self.assertEqual(self.counts(),(1,1,1))
        self.assertEqual(self.uow.events.get_by_id(self.event.event_id),self.event)

    def test_active_transaction_refused_without_committing_or_rolling_it_back(self):
        self.uow.sessions.save(self.session)
        with self.assertRaises(ValueError):self.execute()
        self.assertTrue(self.db.in_transaction)
        self.assertEqual(self.counts(),(1,0,0))
        self.db.rollback()
        self.assertEqual(self.counts(),(0,0,0))

    def test_wrong_subject_and_duplicate_ids_are_rejected_before_writes(self):
        for events in ((replace(self.event,patient_id='PAT-002'),),(self.event,self.event),(None,)):
            with self.subTest(events=events),self.assertRaises(ValueError):self.execute(events)
        self.assertEqual(self.counts(),(0,0,0))

    def test_zero_events_is_valid_and_audited(self):
        self.execute(())
        self.assertEqual(self.counts(),(1,0,1))

    def test_reopen_file_preserves_committed_operation_and_repeat(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'transaction.sqlite3'
            with closing(connect(path)) as db:
                SQLitePatientRepository(db).save(create_patient_context())
                db.commit()
                audit_id=RegisterMultimodalSession(SQLiteMultimodalUnitOfWork(db)).execute(
                    self.session,(self.event,),correlation_id=self.correlation)
            with closing(connect(path)) as db:
                uow=SQLiteMultimodalUnitOfWork(db)
                self.assertEqual(RegisterMultimodalSession(uow).execute(
                    self.session,(self.event,),correlation_id=self.correlation),audit_id)
                self.assertEqual(uow.events.get_by_id(self.event.event_id),self.event)
