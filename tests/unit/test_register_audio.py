from contextlib import closing
from dataclasses import replace
import hashlib
import json
import sqlite3
from unittest.mock import patch
from uuid import uuid4

import pytest

from medassistmultimodal.application.audio import AudioNoSpeechError
from medassistmultimodal.application.process_audio import ProcessedAudio
from medassistmultimodal.application.register_audio import prepare_audio_registration
from medassistmultimodal.application.register_vitals import encode_json
from medassistmultimodal.infrastructure.audio_evidence_store import AudioEvidenceStore
from medassistmultimodal.infrastructure.sqlite_audio_registration import register_audio_sqlite, query_audio_session
from medassistmultimodal.infrastructure.sqlite_multimodal_schema import initialize_multimodal_schema
from medassistmultimodal.infrastructure.sqlite_patient_repository import SQLitePatientRepository
from medassistmultimodal.infrastructure.sqlite_event_repository import SQLiteEventRepository
from medassistmultimodal.infrastructure.sqlite_audit_repository import SQLiteAuditRepository
from tests.unit.test_process_audio import fixture
from tests.unit.test_privacy import create_patient_context


@pytest.fixture
def db():
    with closing(sqlite3.connect(':memory:')) as connection:
        connection.execute('PRAGMA foreign_keys=ON');initialize_multimodal_schema(connection)
        SQLitePatientRepository(connection).save(create_patient_context());connection.commit()
        yield connection


def make(tmp_path,text='Senti tontura.'):
    processor,request,transcriber,run=fixture(tmp_path,text)
    result=processor.execute(request)
    ref=f'data/interim/audio/evidence/{request.run_id}.json'
    return prepare_audio_registration(result,evidence_ref=ref),AudioEvidenceStore(tmp_path),transcriber


def counts(db):
    return tuple(db.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in
                 ('multimodal_sessions','multimodal_events','audit_records'))


@pytest.mark.parametrize('text,expected_count',[
    ('Completei a sessão.',1),('Não senti dor.',2),('Senti tontura.',2),
    ('Ontem senti tontura. Hoje não senti tontura.',3),
])
def test_persist_query_and_retry_without_new_asr(db,tmp_path,text,expected_count):
    prepared,store,transcriber=make(tmp_path,text)
    first=register_audio_sqlite(prepared,connection=db,store=store)
    assert register_audio_sqlite(prepared,connection=db,store=store)==first
    assert counts(db)==(1,expected_count,1)
    transcriber.transcribe_with_details.assert_called_once()
    assert store.read(prepared.evidence_ref)==prepared.evidence
    assert hashlib.sha256(store.read(prepared.evidence_ref)).hexdigest()==prepared.evidence_sha256
    view=query_audio_session(prepared.session.session_id,connection=db,store=store)
    assert len(view['events'])==expected_count and not view['clinical_validation']
    for row in view['events']:
        assert row['event']['source_kind']=='simulated' and row['event']['is_mock'] is True
        assert row['event']['review_status']=='pending_review' and row['event']['confidence'] is None
        assert row['processing_status']=='completed'
    assert json.loads(json.dumps(view))['session']['patient_id']=='PAT-001'


@pytest.mark.parametrize('failure',['audit','second_event'])
def test_rollback_leaves_evidence_for_explicit_retry(db,tmp_path,failure):
    prepared,store,t=make(tmp_path)
    if failure=='audit':
        context=patch.object(SQLiteAuditRepository,'save',side_effect=sqlite3.OperationalError('fixture'))
    else:
        original=SQLiteEventRepository.save;seen=[]
        def save(self,event):
            seen.append(event)
            if len(seen)==2:raise sqlite3.OperationalError('fixture')
            return original(self,event)
        context=patch.object(SQLiteEventRepository,'save',save)
    with context,pytest.raises(sqlite3.OperationalError):
        register_audio_sqlite(prepared,connection=db,store=store)
    assert counts(db)==(0,0,0) and store.read(prepared.evidence_ref)==prepared.evidence
    register_audio_sqlite(prepared,connection=db,store=store)
    assert counts(db)==(1,2,1)


def test_committed_missing_evidence_is_not_recreated(db,tmp_path):
    p,store,t=make(tmp_path);register_audio_sqlite(p,connection=db,store=store)
    path=store.path(p.evidence_ref);path.rename(path.with_suffix('.saved'))
    with pytest.raises(ValueError):register_audio_sqlite(p,connection=db,store=store)
    with pytest.raises(FileNotFoundError):query_audio_session(p.session.session_id,connection=db,store=store)
    assert not path.exists() and counts(db)==(1,2,1)


def test_tampered_evidence_never_overwritten_or_accepted(db,tmp_path):
    p,store,t=make(tmp_path);register_audio_sqlite(p,connection=db,store=store)
    path=store.path(p.evidence_ref);path.write_bytes(b'tampered')
    with pytest.raises(ValueError):register_audio_sqlite(p,connection=db,store=store)
    with pytest.raises(ValueError):query_audio_session(p.session.session_id,connection=db,store=store)
    assert path.read_bytes()==b'tampered' and counts(db)==(1,2,1)


def test_existing_file_conflict_before_transaction(db,tmp_path):
    p,store,t=make(tmp_path);path=store.path(p.evidence_ref);path.parent.mkdir(parents=True);path.write_bytes(b'other')
    with pytest.raises(ValueError):register_audio_sqlite(p,connection=db,store=store)
    assert counts(db)==(0,0,0) and path.read_bytes()==b'other'


def test_same_run_with_new_evidence_conflicts_instead_of_adding_events(db,tmp_path):
    p,store,t=make(tmp_path);register_audio_sqlite(p,connection=db,store=store)
    doc=json.loads(p.evidence);doc['time']['processing_timestamp_utc']='2026-11-07T13:00:00+00:00'
    changed=encode_json(doc)
    q=prepare_audio_registration(ProcessedAudio('completed',changed,hashlib.sha256(changed).hexdigest()),
                                  evidence_ref=p.evidence_ref)
    assert q.events[0].event_id==p.events[0].event_id
    with pytest.raises(ValueError):register_audio_sqlite(q,connection=db,store=store)
    assert store.read(p.evidence_ref)==p.evidence and counts(db)==(1,2,1)


def test_forged_session_metadata_rejected_before_file_or_db(db,tmp_path):
    p,store,t=make(tmp_path)
    forged=replace(p,session=replace(p.session,session_id=uuid4()))
    with pytest.raises(ValueError):register_audio_sqlite(forged,connection=db,store=store)
    assert counts(db)==(0,0,0) and not store.path(p.evidence_ref).exists()


def test_unknown_patient_not_created_implicitly(tmp_path):
    p,store,t=make(tmp_path)
    with closing(sqlite3.connect(':memory:')) as db:
        db.execute('PRAGMA foreign_keys=ON');initialize_multimodal_schema(db)
        with pytest.raises(ValueError):register_audio_sqlite(p,connection=db,store=store)
        assert counts(db)==(0,0,0) and not store.path(p.evidence_ref).exists()


def test_failed_asr_registers_only_technical_summary(db,tmp_path):
    processor,r,t,run=fixture(tmp_path);t.transcribe_with_details.side_effect=AudioNoSpeechError('empty')
    result=processor.execute(r)
    p=prepare_audio_registration(result,evidence_ref=f'data/interim/audio/evidence/{r.run_id}.json')
    assert len(p.events)==1
    store=AudioEvidenceStore(tmp_path);register_audio_sqlite(p,connection=db,store=store)
    view=query_audio_session(p.session.session_id,connection=db,store=store)
    assert view['events'][0]['processing_status']=='failed' and counts(db)==(1,1,1)


def test_rejected_input_cannot_be_registered(tmp_path):
    processor,r,t,run=fixture(tmp_path)
    result=processor.execute(replace(r,permission_declared=False))
    with pytest.raises(ValueError):prepare_audio_registration(result,evidence_ref='data/interim/audio/e.json')


@pytest.mark.parametrize('ref',['../e.json','data/interim/audio/../e.json','data/interim/audio/e.json#x',
    'data/interim/vitals/e.json','data/interim/audio/e.txt'])
def test_evidence_path_restrictions(tmp_path,ref):
    p,store,t=make(tmp_path)
    with pytest.raises(ValueError):prepare_audio_registration(
        ProcessedAudio('completed',p.evidence,p.evidence_sha256),evidence_ref=ref)


def test_missing_session_query(db,tmp_path):
    assert query_audio_session(uuid4(),connection=db,store=AudioEvidenceStore(tmp_path)) is None


def test_reopen_file_database_and_export(tmp_path):
    p,store,t=make(tmp_path);path=tmp_path/'test.sqlite3'
    with closing(sqlite3.connect(path)) as db:
        db.execute('PRAGMA foreign_keys=ON');initialize_multimodal_schema(db)
        SQLitePatientRepository(db).save(create_patient_context());db.commit()
        register_audio_sqlite(p,connection=db,store=store)
    with closing(sqlite3.connect(path)) as db:
        db.execute('PRAGMA foreign_keys=ON')
        view=query_audio_session(p.session.session_id,connection=db,store=store)
        exported=encode_json(view)
        assert json.loads(exported)['events'][0]['event']['source']=='simulated-audio-v1'
        assert register_audio_sqlite(p,connection=db,store=store)>0
        assert counts(db)==(1,2,1)


def test_degraded_llm_keeps_candidates_in_sqlite(db,tmp_path):
    processor,r,t,run=fixture(tmp_path,'Senti tontura.')
    result=processor.execute(replace(r,llm_enabled=True))
    p=prepare_audio_registration(result,evidence_ref='data/interim/audio/degraded.json')
    store=AudioEvidenceStore(tmp_path);register_audio_sqlite(p,connection=db,store=store)
    view=query_audio_session(p.session.session_id,connection=db,store=store)
    assert len(view['events'])==2 and all(e['processing_status']=='degraded' for e in view['events'])
    mention=next(e for e in view['events'] if 'classification' in e['evidence_item'])
    assert mention['evidence_item']['classification']=='candidate_for_human_review'


def test_session_identity_conflict_before_evidence_write(db,tmp_path):
    p,store,t=make(tmp_path);register_audio_sqlite(p,connection=db,store=store)
    doc=json.loads(p.evidence);doc['identity']['run_id']=str(uuid4())
    doc['time']['session_timestamp_utc']='2026-11-07T13:00:00+00:00'
    raw=encode_json(doc)
    changed=prepare_audio_registration(ProcessedAudio('completed',raw,hashlib.sha256(raw).hexdigest()),
                                      evidence_ref='data/interim/audio/other.json')
    with pytest.raises(ValueError):register_audio_sqlite(changed,connection=db,store=store)
    assert counts(db)==(1,2,1) and not store.path(changed.evidence_ref).exists()


def test_changed_reader_prevents_transaction(db,tmp_path):
    p,store,t=make(tmp_path)
    with patch.object(store,'read',return_value=b'changed'),pytest.raises(ValueError):
        register_audio_sqlite(p,connection=db,store=store)
    assert counts(db)==(0,0,0) and store.path(p.evidence_ref).exists()


@pytest.mark.parametrize('fault',['hash','global_state','classification','schema'])
def test_bad_prepared_evidence_rejected(tmp_path,fault):
    p,store,t=make(tmp_path);doc=json.loads(p.evidence)
    if fault=='hash':
        with pytest.raises(ValueError):prepare_audio_registration(
            ProcessedAudio('completed',p.evidence,'0'*64),evidence_ref=p.evidence_ref)
        return
    if fault=='global_state':doc['llm']['status']='timeout'
    elif fault=='classification':doc['rules']['items'][0]['classification']='context_information'
    else:doc={}
    raw=encode_json(doc)
    with pytest.raises(ValueError):prepare_audio_registration(
        ProcessedAudio('completed',raw,hashlib.sha256(raw).hexdigest()),evidence_ref=p.evidence_ref)
