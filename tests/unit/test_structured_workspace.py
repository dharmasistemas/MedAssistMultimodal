from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from unittest.mock import patch
from uuid import UUID, uuid4
import tkinter as tk

import pytest

from medassistmultimodal.application.desktop_history import HistoryError
from medassistmultimodal.application.register_vitals import encode_json
from medassistmultimodal.application.review_event import EventReviewRequest
from medassistmultimodal.demo.synthetic_vitals import write_bundle
from medassistmultimodal.demo.prescription_fixtures import build_prescription_cases
from medassistmultimodal.domain.events import ReviewStatus
from medassistmultimodal.infrastructure.structured_workspace import StructuredWorkspace
from medassistmultimodal.infrastructure.sqlite_multimodal_schema import initialize_multimodal_schema
from medassistmultimodal.infrastructure.sqlite_patient_repository import SQLitePatientRepository
from tests.unit.test_privacy import create_patient_context


@pytest.fixture
def structured(tmp_path):
    write_bundle(tmp_path/'data/synthetic/vitals_v1')
    cases,_=build_prescription_cases();hashes={}
    base=tmp_path/'data/interim/prescriptions/day12_closeout_v1';base.mkdir(parents=True)
    for case,content in cases.items():
        raw=encode_json(content);(base/f'{case}_input.json').write_bytes(raw)
        hashes[f'{case}_input.json']=hashlib.sha256(raw).hexdigest()
    receipt=tmp_path/'reports/DAY_12_TASKS_04_05_2026-11-05.json';receipt.parent.mkdir()
    receipt.write_bytes(encode_json({'artifact_sha256':hashes}))
    source=tmp_path/'history.sqlite3'
    with closing(sqlite3.connect(source)) as c:
        c.execute("PRAGMA foreign_keys=ON");initialize_multimodal_schema(c);SQLitePatientRepository(c).save(create_patient_context());c.commit()
    service=StructuredWorkspace(tmp_path);db=service.create_copy(source.name,'PAT-001')
    return service,db,source


def counts(root,db):
    with closing(sqlite3.connect(root/db)) as c:
        return tuple(c.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
                     for table in ('multimodal_sessions','multimodal_events','audit_records'))


def request(event,**kwargs):
    args=dict(review_id=uuid4(),event_id=UUID(event['event_id']),reviewer_ref='unit-test-only',
        reviewed_at=datetime.now(timezone.utc),reason='Temporary test fixture; not a clinical validation',
        target_status=ReviewStatus.REVIEWED,scope='human_review')
    args.update(kwargs);return EventReviewRequest(**args)


@pytest.mark.parametrize('modality,case,events',[('vitals','V02',2),('vitals','V12',5),('prescriptions','P06',2),('prescriptions','P01',1),('prescriptions','P14',2)])
def test_registration_verified_new_ids_and_exact_retry(tmp_path,structured,modality,case,events):
    s,db,source=structured;before=source.read_bytes()
    result=s.register_scenario(db,'PAT-001',modality,case)
    assert result.persisted
    detail=s.reader.detail(db,UUID(result.session_id)).document
    assert detail['integrity']=='verified' and len(detail['events'])==events
    assert all(r['event']['review_status']=='pending_review' and r['event']['is_mock'] is False for r in detail['events'])
    first=counts(tmp_path,db);assert s.retry_structured(db,result.run_id)==result
    assert counts(tmp_path,db)==first and source.read_bytes()==before
    new=s.register_scenario(db,'PAT-001',modality,case)
    assert new.persisted and new.session_id!=result.session_id


@pytest.mark.parametrize('modality,case',[('vitals','V02'),('prescriptions','P06')])
def test_review_replay_conflict_and_immutable_evidence(tmp_path,structured,modality,case):
    s,db,source=structured;r=s.register_scenario(db,'PAT-001',modality,case)
    detail=s.reader.detail(db,UUID(r.session_id)).document;event=detail['events'][-1]['event']
    evidence=tmp_path/event['evidence_ref'].split('#')[0];before=evidence.read_bytes();source_before=source.read_bytes()
    req=request(event);audit=s.review(db,UUID(r.session_id),req,event['evidence_ref'])
    assert s.review(db,UUID(r.session_id),req,event['evidence_ref'])==audit
    d=s.reader.detail(db,UUID(r.session_id)).document
    assert len(d['review_histories'][event['event_id']])==1
    assert next(e['event']['review_status'] for e in d['events'] if e['event']['event_id']==event['event_id'])=='reviewed'
    with pytest.raises(HistoryError,match='review_conflict'):s.review(db,UUID(r.session_id),request(event),event['evidence_ref'])
    with pytest.raises(HistoryError,match='registration_conflict'):s.retry_structured(db,r.run_id)
    assert evidence.read_bytes()==before and source.read_bytes()==source_before


@pytest.mark.parametrize('failure',['hash','missing','reference','session','technical'])
def test_invalid_review_does_not_write(tmp_path,structured,failure):
    s,db,_=structured;r=s.register_scenario(db,'PAT-001','vitals','V02')
    event=s.reader.detail(db,UUID(r.session_id)).document['events'][-1]['event'];ref=event['evidence_ref'];session=UUID(r.session_id)
    req=request(event,**({'scope':'technical_simulation'} if failure=='technical' else {}))
    if failure=='hash':(tmp_path/ref.split('#')[0]).write_bytes(b'changed')
    if failure=='missing':(tmp_path/ref.split('#')[0]).rename(tmp_path/'saved.json')
    if failure=='reference':ref+='changed'
    if failure=='session':session=uuid4()
    before=(tmp_path/db).read_bytes()
    with pytest.raises(HistoryError):s.review(db,session,req,ref)
    assert (tmp_path/db).read_bytes()==before


@pytest.mark.parametrize('failure',['history','patient','catalog','changed','missing'])
def test_rejected_registration_preserves_database(tmp_path,structured,failure):
    s,db,source=structured;patient='PAT-001';case='V02'
    if failure=='history':db=source.name
    if failure=='patient':patient='PAT-999'
    if failure=='catalog':case='V99'
    if failure=='changed':(tmp_path/'data/synthetic/vitals_v1/V02.json').write_bytes(b'changed')
    if failure=='missing':(tmp_path/'data/synthetic/vitals_v1/V02.json').rename(tmp_path/'saved.json')
    before=(tmp_path/db).read_bytes()
    with pytest.raises(HistoryError):s.register_scenario(db,patient,'vitals',case)
    assert (tmp_path/db).read_bytes()==before and not s.structured_prepared


def test_failed_save_retains_exact_bytes_for_retry(tmp_path,structured):
    s,db,_=structured
    with patch('medassistmultimodal.infrastructure.structured_workspace.register_prepared_vitals',side_effect=sqlite3.OperationalError('test-only')):
        r=s.register_scenario(db,'PAT-001','vitals','V02')
    assert not r.persisted
    prepared=s.structured_prepared[r.run_id][-1];path=tmp_path/prepared.events[0].evidence_ref.split('#')[0];before=path.read_bytes()
    assert counts(tmp_path,db)==(0,0,0)
    with patch('medassistmultimodal.infrastructure.structured_workspace.prepare_vitals',side_effect=AssertionError('must not recompute')):
        assert s.retry_structured(db,r.run_id).persisted
    assert path.read_bytes()==before and counts(tmp_path,db)==(1,2,1)


def test_retry_other_workspace_or_missing_cache_rejected(tmp_path,structured):
    s,db,source=structured;r=s.register_scenario(db,'PAT-001','vitals','V02');other=s.create_copy(source.name,'PAT-001')
    with pytest.raises(HistoryError,match='workspace_required'):s.retry_structured(other,r.run_id)
    with pytest.raises(HistoryError,match='no_pending_registration'):StructuredWorkspace(tmp_path).retry_structured(db,r.run_id)


def test_conflicting_evidence_preserved(tmp_path,structured):
    s,db,_=structured
    with patch.object(s,'_persist',side_effect=sqlite3.OperationalError('test-only')):r=s.register_scenario(db,'PAT-001','prescriptions','P06')
    p=s.structured_prepared[r.run_id][-1];file=tmp_path/p.events[0].evidence_ref.split('#')[0];file.write_bytes(b'preserve')
    with pytest.raises(HistoryError,match='evidence_conflict'):s.retry_structured(db,r.run_id)
    assert file.read_bytes()==b'preserve' and counts(tmp_path,db)==(0,0,0)


def check_tk_structured_registration_and_review(tmp_path,structured,tk_runtime):
    from tests.unit.test_desktop_workflow import pump
    from medassistmultimodal.desktop_multimodal import MultimodalApp
    s,db,_=structured;root=tk.Toplevel(tk_runtime);root.withdraw()
    app=MultimodalApp(root,reader=s.reader,workspace=s,project_root=tmp_path)
    try:
        app.database.set(db);app.load_history();pump(root,app)
        with patch('medassistmultimodal.desktop_multimodal.messagebox.askyesno',return_value=False):app.register_structured_scenario()
        assert not app.worker.busy and not app.sessions.get_children()
        for modality,case in [('Vitais','V02'),('Prescrições','P06')]:
            app.structured_modality.set(modality);app.refresh_structured_cases();app.structured_case.set(case)
            with patch('medassistmultimodal.desktop_multimodal.messagebox.askyesno',return_value=True):app.register_structured_scenario()
            pump(root,app)
            sid=next(row.session_id for row in app.state.rows if modality in row.modalities)
            app.sessions.selection_set(sid);app.select_session();pump(root,app)
            event=app.events.get_children()[-1];app.events.selection_set(event);app.select_event()
            app.reviewer.set('unit-test-only');app.reason.set('Automated widget test on temporary database only')
            with patch('medassistmultimodal.desktop_workflow.messagebox.askyesno',return_value=True):app.submit_review(ReviewStatus.REVIEWED)
            pump(root,app);app.retry_review();pump(root,app)
            assert len(s.reader.detail(db,UUID(sid)).document['review_histories'][event])==1
        assert len(app.sessions.get_children())==2
        app.patient.set('PAT-999')
        with patch('medassistmultimodal.desktop_multimodal.messagebox.askyesno') as confirm:app.register_structured_scenario()
        confirm.assert_not_called();assert 'Consultar' in app.status.get()
    finally:
        if app.worker.busy:app.worker.thread.join(3);app.worker.drain()
        root.after_cancel(app.poll_id);root.destroy()
