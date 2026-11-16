from dataclasses import replace
import hashlib
import json
import sqlite3
from uuid import uuid4

import pytest

from medassistmultimodal.application.desktop_history import HistoryError, HistoryState, SessionDetail
from medassistmultimodal.application.review_event import EventReviewRequest
from medassistmultimodal.domain.events import ReviewStatus
from medassistmultimodal.desktop import audio_text
from medassistmultimodal.infrastructure.desktop_history import SQLiteHistoryReader
from medassistmultimodal.infrastructure.sqlite_audio_registration import register_audio_sqlite
from medassistmultimodal.infrastructure.sqlite_event_review import review_event_sqlite
from medassistmultimodal.infrastructure.sqlite_multimodal_schema import initialize_multimodal_schema
from medassistmultimodal.infrastructure.sqlite_patient_repository import SQLitePatientRepository
from medassistmultimodal.infrastructure.sqlite_session_repository import SQLiteSessionRepository
from tests.unit.test_register_audio import make
from tests.unit.test_privacy import create_patient_context


@pytest.fixture
def persisted(tmp_path):
    path = tmp_path/'history.sqlite3'
    with sqlite3.connect(path) as connection:
        connection.execute('PRAGMA foreign_keys=ON')
        initialize_multimodal_schema(connection)
        SQLitePatientRepository(connection).save(create_patient_context()); connection.commit()
        prepared, store, transcriber = make(tmp_path)
        register_audio_sqlite(prepared, connection=connection, store=store)
    return path, prepared, store, transcriber


def test_verified_detail_and_history_are_read_only(tmp_path, persisted):
    path, prepared, store, transcriber = persisted
    before = path.read_bytes(), store.read(prepared.evidence_ref)
    reader = SQLiteHistoryReader(tmp_path)
    rows = reader.sessions(path.name, 'PAT-001')
    assert len(rows)==1 and rows[0].session_id==str(prepared.session.session_id)
    detail = reader.detail(path.name, prepared.session.session_id)
    data = detail.document
    assert data['integrity']=='verified' and data['access_mode']=='read_only'
    assert data['documents'][0]['evidence']==json.loads(prepared.evidence)
    assert 'Voz sintética (TTS)' in audio_text(detail) and 'mock' in audio_text(detail)
    assert 'tontura' in audio_text(detail)
    data['documents'].clear()
    assert detail.document['documents']
    assert before==(path.read_bytes(), store.read(prepared.evidence_ref))
    transcriber.transcribe_with_details.assert_called_once()


@pytest.mark.parametrize('database', ['absent.db', '../outside.db', '_backup/private.db', '.git/config'])
def test_missing_private_or_outside_database_not_created(tmp_path, database):
    with pytest.raises(HistoryError) as exc:
        SQLiteHistoryReader(tmp_path).sessions(database, 'PAT-001')
    assert exc.value.code=='database_unavailable'
    assert not (tmp_path/'absent.db').exists()


def test_invalid_schema_and_patient_are_explicit_errors(tmp_path):
    path=tmp_path/'empty.db'
    with sqlite3.connect(path): pass
    reader=SQLiteHistoryReader(tmp_path)
    with pytest.raises(HistoryError, match='history_unavailable'): reader.sessions(path.name, 'PAT-001')
    with pytest.raises(HistoryError, match='invalid_patient'): reader.sessions(path.name, 'real-person')


def test_empty_patient_and_session_without_audio_differ(tmp_path, persisted):
    path, p, store, _ = persisted;reader=SQLiteHistoryReader(tmp_path)
    assert reader.sessions(path.name, 'PAT-999')==()
    session=replace(p.session, session_id=uuid4())
    with sqlite3.connect(path) as connection:
        connection.execute('PRAGMA foreign_keys=ON')
        SQLiteSessionRepository(connection).save(session)
    detail=reader.detail(path.name, session.session_id)
    assert detail.document['integrity']=='not_checked'
    assert 'não contém eventos de áudio' in audio_text(detail)
    with pytest.raises(HistoryError, match='session_not_found'):reader.detail(path.name,uuid4())


@pytest.mark.parametrize('failure,code', [('missing','evidence_missing'),('tampered','evidence_invalid'),('unsupported','evidence_unsupported')])
def test_unverified_evidence_never_reaches_presentation(tmp_path,persisted,failure,code):
    path,p,store,_=persisted;evidence=store.path(p.evidence_ref)
    if failure=='missing':evidence.rename(evidence.with_suffix('.saved'))
    elif failure=='tampered':evidence.write_bytes(b'changed')
    else:
        doc=json.loads(p.evidence);doc['schema_version']='unsupported';evidence.write_text(json.dumps(doc))
    with pytest.raises(HistoryError,match=code):SQLiteHistoryReader(tmp_path).detail(path.name,p.session.session_id)


def test_review_status_and_audit_from_database_do_not_change_original_evidence(tmp_path,persisted):
    path,p,store,_=persisted;before=store.read(p.evidence_ref)
    request=EventReviewRequest(review_id=uuid4(),event_id=p.events[-1].event_id,
        reviewer_ref='fixture-reviewer',reviewed_at=p.session.started_at,reason='Teste técnico explícito',
        target_status=ReviewStatus.REVIEWED,scope='technical_simulation')
    with sqlite3.connect(path) as connection:
        connection.execute('PRAGMA foreign_keys=ON');review_event_sqlite(request,connection=connection)
    detail=SQLiteHistoryReader(tmp_path).detail(path.name,p.session.session_id).document
    row=next(r for r in detail['events'] if r['event']['event_id']==str(request.event_id))
    assert row['event']['review_status']=='reviewed'
    assert len(detail['review_histories'][str(request.event_id)])==1
    assert before==store.read(p.evidence_ref)


def test_stale_results_and_failure_clear_previous_detail():
    state=HistoryState();old=state.begin('old');current=state.begin('current')
    detail=SessionDetail(b'{}')
    assert not state.receive_detail(old,detail)
    assert state.receive_detail(current,detail)
    new=state.begin('new');assert state.detail is None
    assert not state.fail(old,'old_error')
    assert state.fail(new,'evidence_invalid') and state.detail is None and state.status=='error'


def test_service_connection_is_query_only(tmp_path,persisted):
    path,_,_,_=persisted
    with SQLiteHistoryReader(tmp_path)._connection(path.name) as connection:
        with pytest.raises(sqlite3.OperationalError):
            connection.execute("DELETE FROM multimodal_events")
