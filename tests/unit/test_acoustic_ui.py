from datetime import datetime,timezone
import hashlib
import json
from uuid import UUID,uuid4
from unittest.mock import patch

import pytest

from medassistmultimodal.application.desktop_history import HistoryError
from medassistmultimodal.application.register_acoustics import restore_acoustics
from medassistmultimodal.infrastructure.desktop_text import TextWorkspace
from medassistmultimodal.infrastructure.desktop_summary import SummaryService
from medassistmultimodal.providers.acoustic_local import LocalPauseAnalyzer,AcousticDecoderUnavailable
from tests.unit.test_structured_workspace import structured,counts,request
from tests.unit.test_internal_pauses import samples


@pytest.fixture
def acoustic_db(tmp_path,structured,monkeypatch):
    _,db,source=structured
    directory=tmp_path/'data/interim/audio/elevenlabs_tests';directory.mkdir(parents=True)
    def origin(root,case):
        path=directory/f'{case}.mp3'
        if not path.exists():path.write_bytes(case.encode())
        return dict(case_id=case,audio_ref=path.relative_to(tmp_path).as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            origin_kind='tts',permission_declared=True,permission_ref='fixture-permission',voice_name='Fixture',tts_model='Fixture')
    monkeypatch.setattr('medassistmultimodal.infrastructure.structured_workspace.acoustic_source',origin)
    def decoder(path,**kwargs):
        import numpy as np
        case=path.split('/')[-1].split('\\')[-1]
        if case=='AP01.mp3':return samples(intervals=())
        if case=='AP02.mp3':return np.zeros(80000)
        return samples()
    service=TextWorkspace(tmp_path,pause_analyzer_factory=lambda:LocalPauseAnalyzer(tmp_path,decoder=decoder))
    return service,db,source


@pytest.mark.parametrize('case,status,candidates',[('AP01','no_signal',0),('AP02','insufficient_evidence',0),('AP03','signal',1)])
def test_acoustic_persistence_reader_summary_and_retry(tmp_path,acoustic_db,case,status,candidates):
    s,db,source=acoustic_db;before=source.read_bytes()
    r=s.register_scenario(db,'PAT-001','acoustics',case);assert r.persisted
    d=s.reader.detail(db,UUID(r.session_id)).document
    doc=d['acoustics'][0]['evidence'];assert doc['assessment']['status']==status
    assert len(doc['candidates'])==candidates and len(d['events'])==1+candidates
    assert doc['asr']==doc['llm']=='not_run' and all(x['event']['is_mock'] for x in d['events'])
    ref=d['acoustics'][0]['reference'];prepared=restore_acoustics(doc,ref)
    assert prepared.evidence==(tmp_path/ref).read_bytes()
    first=counts(tmp_path,db);assert s.retry_structured(db,r.run_id)==r
    assert counts(tmp_path,db)==first and source.read_bytes()==before
    reports=SummaryService(tmp_path);snapshot=reports.build(db,'PAT-001',[r.session_id]);reports.export(snapshot)
    assert 'ASR e LLM não executados' in snapshot.document['text']


def test_review_and_evidence_no_reset(tmp_path,acoustic_db):
    s,db,_=acoustic_db;r=s.register_scenario(db,'PAT-001','acoustics','AP03')
    d=s.reader.detail(db,UUID(r.session_id)).document;e=next(x['event'] for x in d['events'] if '/candidates/' in x['event']['evidence_ref'])
    p=tmp_path/e['evidence_ref'].split('#')[0];before=p.read_bytes()
    req=request(e,scope='technical_simulation');audit=s.review(db,UUID(r.session_id),req,e['evidence_ref'])
    assert s.review(db,UUID(r.session_id),req,e['evidence_ref'])==audit
    with pytest.raises(HistoryError,match='registration_conflict'):s.retry_structured(db,r.run_id)
    assert p.read_bytes()==before


@pytest.mark.parametrize('failure',['hash','missing','group','event'])
def test_bad_acoustic_evidence_blocked(tmp_path,acoustic_db,failure):
    import sqlite3
    s,db,_=acoustic_db;r=s.register_scenario(db,'PAT-001','acoustics','AP03')
    d=s.reader.detail(db,UUID(r.session_id)).document;ref=d['acoustics'][0]['reference'];p=tmp_path/ref
    if failure=='hash':p.write_bytes(b'changed')
    elif failure=='missing':p.rename(tmp_path/'preserved.json')
    else:
        with sqlite3.connect(tmp_path/db) as c:
            e=d['events'][-1]['event']['event_id']
            if failure=='group':c.execute('DELETE FROM multimodal_events WHERE event_id=?',(e,))
            else:c.execute('UPDATE multimodal_events SET is_mock=0 WHERE event_id=?',(e,))
    with pytest.raises(HistoryError):s.reader.detail(db,UUID(r.session_id))


def test_invalid_patient_or_case_does_not_decode(acoustic_db):
    s,db,_=acoustic_db;factory=s.pause_analyzer_factory
    with patch.object(s,'pause_analyzer_factory') as make:
        with pytest.raises(HistoryError):s.register_scenario(db,'PAT-999','acoustics','AP01')
        with pytest.raises(HistoryError):s.register_scenario(db,'PAT-001','acoustics','AP04')
    make.assert_not_called()


def test_decoder_failure_not_a_negative(acoustic_db):
    s,db,_=acoustic_db
    class Failure:
        def analyze(self,*args,**kwargs):raise AcousticDecoderUnavailable('Fixture')
    s.pause_analyzer_factory=Failure
    with pytest.raises(HistoryError,match='acoustic_decoder_unavailable'):s.register_scenario(db,'PAT-001','acoustics','AP01')


def check_tk_acoustic_registration(tmp_path,acoustic_db,tk_runtime):
    import tkinter as tk
    from tests.unit.test_desktop_workflow import pump
    from medassistmultimodal.desktop_summary import SummaryApp
    s,db,_=acoustic_db;root=tk.Toplevel(tk_runtime);root.withdraw()
    app=SummaryApp(root,reader=s.reader,workspace=s,project_root=tmp_path)
    try:
        app.database.set(db);app.load_history();pump(root,app)
        app.structured_modality.set('Pausas de áudio');app.refresh_structured_cases();app.structured_case.set('AP03')
        assert tuple(app.structured_choices.cget('values'))==('AP01','AP02','AP03')
        with patch('medassistmultimodal.desktop_multimodal.messagebox.askyesno',return_value=True):app.register_structured_scenario()
        pump(root,app)
        sid=app.last_structured.get().split('Nova sessão: ')[1].split(' |')[0]
        app.sessions.selection_set(sid);app.select_session();pump(root,app)
        assert 'Padrão experimental de pausas' in app.audio.get('1.0','end')
        assert 'ASR e LLM não executados' in app.audio.get('1.0','end')
        assert any('Pausas frequentes' in str(app.events.item(x,'values')) for x in app.events.get_children())
        app.load_report_catalog();pump(root,app);app.report_sessions.selection_set(sid);root.update()
        app.generate_report();pump(root,app);assert app.report_snapshot is not None
        app.export_report();pump(root,app)
    finally:
        if app.worker.busy:app.worker.thread.join(3);app.worker.drain()
        root.after_cancel(app.poll_id);root.destroy()
