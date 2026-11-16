from contextlib import closing
from dataclasses import replace
import hashlib
import json
import sqlite3
import tkinter as tk
from uuid import UUID,uuid4

import pytest

from medassistmultimodal.application.desktop_history import HistoryError
from medassistmultimodal.infrastructure.desktop_summary import SummaryService
from medassistmultimodal.infrastructure.desktop_text import TextHistoryReader
from medassistmultimodal.infrastructure.desktop_video import VideoWorkspace
from medassistmultimodal.infrastructure.sqlite_audio_registration import register_audio_sqlite
from tests.unit.test_structured_workspace import structured,request
from tests.unit.test_desktop_video import prepare_fixture
from tests.unit.test_register_audio import make


@pytest.fixture
def summary_data(tmp_path,structured):
    _,database,source=structured;workspace=VideoWorkspace(tmp_path)
    a,store,transcriber=make(tmp_path,text="Não senti dor.")
    with closing(sqlite3.connect(tmp_path/database)) as c:
        c.execute('PRAGMA foreign_keys=ON');register_audio_sqlite(a,connection=c,store=store)
    v=workspace.register_scenario(database,'PAT-001','vitals','V02')
    p=workspace.register_scenario(database,'PAT-001','prescriptions','P06')
    ref=(workspace.writable_path(database).parent/'video_fixture.json').relative_to(tmp_path).as_posix()
    video=prepare_fixture(ref);workspace._persist_video(database,video)
    ids=[str(a.session.session_id),v.session_id,p.session_id,str(video.session.session_id)]
    return SummaryService(tmp_path),database,ids,workspace,source,transcriber


def test_summary_four_modalities_separate_identities_no_provider_or_write(tmp_path,summary_data):
    service,db,ids,w,source,transcriber=summary_data;before=(tmp_path/db).read_bytes();original=source.read_bytes()
    snapshot=service.build(db,'PAT-001',ids);d=snapshot.document
    assert len(d['patient_sessions'])==3 and len(d['dataset_sessions'])==1
    assert d['dataset_sessions'][0]['session']['patient_id'] is None
    assert set(d['counts']['by_modality'])=={'audio','vitals','prescriptions','video'}
    assert d['causal_correlation_validated'] is False and d['clinical_validation'] is False
    assert 'DATASET INDEPENDENTE' in d['text'] and 'Não senti dor' in d['text']
    assert '120' in d['text'] and '10 mg' in d['text'] and '15 mg' in d['text']
    assert (tmp_path/db).read_bytes()==before and source.read_bytes()==original
    transcriber.transcribe_with_details.assert_called_once()  # Fixture preparation only.


def test_export_json_txt_hash_manifest_and_idempotent_retry(tmp_path,summary_data):
    service,db,ids,_,_,_=summary_data;snapshot=service.build(db,'PAT-001',ids)
    ref=service.export(snapshot);assert service.export(snapshot)==ref
    directory=tmp_path/ref;manifest=json.loads((directory/'manifest.json').read_bytes())
    assert json.loads((directory/'summary.json').read_bytes())==snapshot.document
    assert (directory/'summary.txt').read_text(encoding='utf-8')==snapshot.document['text']
    for name,expected in manifest['sha256'].items():assert hashlib.sha256((directory/name).read_bytes()).hexdigest()==expected


@pytest.mark.parametrize('ids',[[],['invalid'],[str(uuid4())],['same']*21])
def test_bad_selection_rejected(summary_data,ids):
    service,db,_,_,_,_=summary_data
    with pytest.raises(HistoryError):service.build(db,'PAT-001',ids)


def test_duplicate_and_other_patient_session_rejected(summary_data):
    service,db,ids,_,_,_=summary_data
    with pytest.raises(HistoryError):service.build(db,'PAT-001',[ids[0],ids[0]])
    with pytest.raises(HistoryError):service.build(db,'PAT-002',[ids[0]])


def test_review_change_blocks_export_until_rebuilt(tmp_path,summary_data):
    service,db,ids,w,_,_=summary_data;snapshot=service.build(db,'PAT-001',ids)
    d=w.reader.detail(db,UUID(ids[1])).document;e=d['events'][-1]['event']
    w.review(db,UUID(ids[1]),request(e),e['evidence_ref'])
    with pytest.raises(HistoryError,match='report_stale'):service.export(snapshot)
    fresh=service.build(db,'PAT-001',ids)
    assert fresh.document['counts']['review_status']['reviewed']==1
    assert service.export(fresh)


@pytest.mark.parametrize('failure',['missing','changed'])
def test_bad_evidence_blocks_generation_and_export(tmp_path,summary_data,failure):
    service,db,ids,w,_,_=summary_data;snapshot=service.build(db,'PAT-001',ids)
    ref=snapshot.document['patient_sessions'][0]
    record=next(r for area in ('documents','vitals','prescriptions') for r in ref[area]);file=tmp_path/record['reference']
    if failure=='missing':file.rename(tmp_path/'saved.json')
    else:file.write_bytes(b'changed')
    with pytest.raises(HistoryError):service.build(db,'PAT-001',ids)
    with pytest.raises(HistoryError):service.export(snapshot)


def test_partial_export_not_overwritten(tmp_path,summary_data):
    service,db,ids,_,_,_=summary_data;snapshot=service.build(db,'PAT-001',ids)
    directory=tmp_path/f"data/interim/multimodal/reports_v1/{snapshot.document['report_id']}";directory.mkdir(parents=True)
    (directory/'summary.txt').write_bytes(b'preserve')
    with pytest.raises(HistoryError,match='report_export_conflict'):service.export(snapshot)
    assert (directory/'summary.txt').read_bytes()==b'preserve'


def test_summary_without_optional_modality_and_quality_is_not_normality(tmp_path,summary_data):
    service,db,ids,w,_,_=summary_data
    extra=w.register_scenario(db,'PAT-001','vitals','V12')
    snapshot=service.build(db,'PAT-001',[extra.session_id])
    assert not snapshot.document['dataset_sessions'] and '0/12 válidas' in snapshot.document['text']
    assert 'não significa normalidade' in snapshot.document['text']


def test_tampered_summary_text_is_not_exported(summary_data):
    from medassistmultimodal.application.register_vitals import encode_json
    service,db,ids,_,_,_=summary_data;s=service.build(db,'PAT-001',ids);d=s.document;d['text']='invented diagnosis'
    with pytest.raises(HistoryError):service.export(replace(s,payload=encode_json(d)))


def check_tk_summary_selection_generation_export_and_context(tmp_path,summary_data,tk_runtime):
    from tests.unit.test_desktop_workflow import pump
    from medassistmultimodal.desktop_summary import SummaryApp
    from medassistmultimodal.infrastructure.desktop_text import TextWorkspace
    service,db,ids,_,_,_=summary_data;root=tk.Toplevel(tk_runtime);root.withdraw();w=TextWorkspace(tmp_path)
    app=SummaryApp(root,reader=w.reader,workspace=w,project_root=tmp_path)
    try:
        app.database.set(db);app.load_history();pump(root,app);app.load_report_catalog();pump(root,app)
        assert len(app.report_sessions.get_children())==4
        app.report_sessions.selection_set(ids);root.update();app.generate_report();pump(root,app)
        assert app.report_snapshot is not None and 'DATASET INDEPENDENTE' in app.report_text.get('1.0','end')
        app.export_report();pump(root,app);assert 'Exportação concluída:' in app.status.get()
        app.report_sessions.selection_set(ids[:1]);root.update();assert app.report_snapshot is None
        app.patient.set('PAT-002');assert not app.report_sessions.get_children()
        app.export_report();assert 'Consulte primeiro' in app.status.get()
    finally:
        if app.worker.busy:app.worker.thread.join(3);app.worker.drain()
        root.after_cancel(app.poll_id);root.destroy()


def test_concurrent_database_change_rejects_mixed_snapshot(tmp_path,summary_data):
    from unittest.mock import patch
    service,db,ids,_,_,_=summary_data;original=service.reader.detail;changed=[]
    def detail(database,session):
        result=original(database,session)
        if not changed:
            with closing(sqlite3.connect(tmp_path/db)) as c:
                c.execute("UPDATE multimodal_events SET review_status='reviewed' WHERE event_id=?",(result.document['events'][0]['event']['event_id'],));c.commit()
            changed.append(True)
        return result
    with patch.object(service.reader,'detail',side_effect=detail):
        with pytest.raises(HistoryError,match='report_stale'):service.build(db,'PAT-001',ids)


def test_unsupported_source_is_not_silently_omitted(tmp_path,summary_data):
    service,db,ids,_,_,_=summary_data
    with closing(sqlite3.connect(tmp_path/db)) as c:
        c.execute("UPDATE multimodal_events SET source='unknown-source' WHERE session_id=?",(ids[0],));c.commit()
    with pytest.raises(HistoryError,match='evidence_unsupported'):service.build(db,'PAT-001',ids)


def test_export_mixed_review_states_independent_of_json_key_order(summary_data):
    from medassistmultimodal.infrastructure.desktop_summary import factual_text
    service,db,ids,workspace,_,_=summary_data
    initial=service.build(db,'PAT-001',ids).document
    # Make the first counted event reviewed, so insertion order differs from sorted JSON.
    first=initial['patient_sessions'][0];event=first['events'][0]['event']
    workspace.review(db,UUID(first['session']['session_id']),request(event),event['evidence_ref'])
    snapshot=service.build(db,'PAT-001',ids);document=snapshot.document
    assert document['counts']['review_status']['reviewed']==1
    assert document['counts']['review_status']['pending_review']>0
    assert document['text']==factual_text(json.loads(json.dumps(document,sort_keys=True)))
    assert service.export(snapshot)
