from contextlib import closing
from dataclasses import replace
from datetime import datetime,timezone
import sqlite3
from unittest.mock import patch
from uuid import uuid4

import pytest

from medassistmultimodal.application.review_event import EventReviewRequest
from medassistmultimodal.domain.events import ReviewStatus
from medassistmultimodal.infrastructure.sqlite_event_review import review_event_sqlite,event_review_history
from medassistmultimodal.infrastructure.sqlite_audio_registration import register_audio_sqlite,query_audio_session
from medassistmultimodal.infrastructure.sqlite_audit_repository import SQLiteAuditRepository
from medassistmultimodal.infrastructure.sqlite_event_repository import SQLiteEventRepository
from medassistmultimodal.infrastructure.sqlite_multimodal_schema import initialize_multimodal_schema
from medassistmultimodal.infrastructure.sqlite_patient_repository import SQLitePatientRepository
from tests.unit.test_register_audio import make,counts
from tests.unit.test_privacy import create_patient_context


@pytest.fixture
def ready(tmp_path):
    prepared,store,transcriber=make(tmp_path)
    with closing(sqlite3.connect(':memory:')) as db:
        db.execute('PRAGMA foreign_keys=ON');initialize_multimodal_schema(db)
        SQLitePatientRepository(db).save(create_patient_context());db.commit()
        register_audio_sqlite(prepared,connection=db,store=store)
        yield db,prepared,store


def request(event_id,**kwargs):
    values=dict(review_id=uuid4(),event_id=event_id,reviewer_ref='fixture-reviewer',
        reviewed_at=datetime(2026,11,7,14,tzinfo=timezone.utc),reason='Offline technical fixture review',
        target_status=ReviewStatus.REVIEWED,scope='technical_simulation')
    values.update(kwargs);return EventReviewRequest(**values)


@pytest.mark.parametrize('target',[ReviewStatus.REVIEWED,ReviewStatus.DISMISSED])
def test_review_and_exact_retry_preserve_evidence_and_metadata(ready,target):
    db,p,store=ready;event=p.events[1];r=request(event.event_id,target_status=target)
    before=store.read(p.evidence_ref)
    first=review_event_sqlite(r,connection=db)
    assert review_event_sqlite(r,connection=db)==first
    actual=SQLiteEventRepository(db).get_by_id(event.event_id)
    assert actual==replace(event,review_status=target) and store.read(p.evidence_ref)==before
    assert counts(db)==(1,2,2)
    history=event_review_history(event.event_id,connection=db)
    assert len(history)==1 and history[0]['events'][0]['reviewer_ref']=='fixture-reviewer'
    assert history[0]['events'][0]['scope']=='technical_simulation'
    assert history[0]['events'][0]['clinical_validation'] is False
    view=query_audio_session(p.session.session_id,connection=db,store=store)
    item=next(row for row in view['events'] if row['event']['event_id']==str(event.event_id))
    assert item['event']['review_status']==target
    assert item['evidence_item']['review_status']=='pending_review'
    with pytest.raises(ValueError):register_audio_sqlite(p,connection=db,store=store)
    assert SQLiteEventRepository(db).get_by_id(event.event_id).review_status==target


def test_review_and_audit_rollback_together(ready):
    db,p,store=ready;r=request(p.events[1].event_id)
    with patch.object(SQLiteAuditRepository,'save',side_effect=sqlite3.OperationalError('fixture')):
        with pytest.raises(sqlite3.OperationalError):review_event_sqlite(r,connection=db)
    assert counts(db)==(1,2,1)
    assert SQLiteEventRepository(db).get_by_id(r.event_id).review_status==ReviewStatus.PENDING_REVIEW
    review_event_sqlite(r,connection=db)
    assert len(event_review_history(r.event_id,connection=db))==1


@pytest.mark.parametrize('change',['reason','target','reviewer','time','event'])
def test_review_id_conflict_cannot_change_existing_receipt(ready,change):
    db,p,store=ready;r=request(p.events[1].event_id);review_event_sqlite(r,connection=db)
    changes={'reason':dict(reason='Different reason'),'target':dict(target_status=ReviewStatus.DISMISSED),
             'reviewer':dict(reviewer_ref='other-fixture'),'time':dict(reviewed_at=datetime(2026,11,7,15,tzinfo=timezone.utc)),
             'event':dict(event_id=p.events[0].event_id)}
    with pytest.raises(ValueError):review_event_sqlite(replace(r,**changes[change]),connection=db)
    assert counts(db)==(1,2,2)
    assert SQLiteEventRepository(db).get_by_id(r.event_id).review_status==ReviewStatus.REVIEWED


def test_new_review_id_does_not_silently_reopen_event(ready):
    db,p,store=ready;r=request(p.events[0].event_id);review_event_sqlite(r,connection=db)
    with pytest.raises(ValueError):review_event_sqlite(replace(r,review_id=uuid4()),connection=db)
    assert counts(db)==(1,2,2)


def test_missing_event_no_audit_written(ready):
    db,p,store=ready
    with pytest.raises(ValueError):review_event_sqlite(request(uuid4()),connection=db)
    assert counts(db)==(1,2,1)


@pytest.mark.parametrize('change',[
    dict(reviewer_ref=''),dict(reviewer_ref='Personal Name'),dict(reason=''),dict(reason='x'*501),
    dict(reason='line\nbreak'),dict(target_status=ReviewStatus.PENDING_REVIEW),dict(target_status='reviewed'),
    dict(expected_status=ReviewStatus.REVIEWED),dict(reviewed_at=datetime(2026,11,7)),dict(scope='automatic'),
])
def test_invalid_review_request_rejected(change):
    with pytest.raises(ValueError):request(uuid4(),**change)


def test_technical_simulation_cannot_review_nonmock_event(ready):
    db,p,store=ready
    event=replace(p.events[1],event_id=uuid4(),is_mock=False)
    SQLiteEventRepository(db).save(event);db.commit()
    with pytest.raises(ValueError):review_event_sqlite(request(event.event_id),connection=db)
    assert SQLiteEventRepository(db).get_by_id(event.event_id).review_status==ReviewStatus.PENDING_REVIEW
    assert event_review_history(event.event_id,connection=db)==()


def test_declared_human_review_metadata_is_distinct_from_simulation(ready):
    db,p,store=ready
    r=request(p.events[1].event_id,scope='human_review',reviewer_ref='human-fixture-01')
    review_event_sqlite(r,connection=db)
    history=event_review_history(r.event_id,connection=db)
    assert history[0]['events'][0]['scope']=='human_review'
    assert history[0]['events'][0]['reviewed_at'].endswith('+00:00')
    assert history[0]['events'][0]['clinical_validation'] is False


def test_pending_event_has_no_review_receipt(ready):
    db,p,store=ready
    assert event_review_history(p.events[0].event_id,connection=db)==()
