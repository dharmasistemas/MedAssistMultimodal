from datetime import datetime,timezone
from dataclasses import replace
import json
import sqlite3
import tkinter as tk
from unittest.mock import Mock,patch
from uuid import UUID

import pytest

from medassistmultimodal.application.desktop_history import HistoryError
from medassistmultimodal.application.llm import LLMProviderTimeoutError,LLMProviderUnavailableError
from medassistmultimodal.infrastructure.desktop_text import TextWorkspace,PromptV2Bridge,PROMPT_V2,ORIGINAL_PROMPT,PROMPT_SHA256,validate_optional_text
from tests.unit.test_desktop_history import persisted


@pytest.fixture
def text_workspace(tmp_path,persisted):
    from tests.unit.test_desktop_workflow import corpus_fixture
    source,_,_,_=persisted;transcriber=corpus_fixture(tmp_path)
    provider=Mock();provider.generate.return_value=json.dumps(dict(sentiment='neutral',sentiment_evidence=[{'quote':'Não senti dor.'}],terms=[{'term':'dor','quote':'Não senti dor.'}]))
    factory=Mock(return_value=provider)
    service=TextWorkspace(tmp_path,transcriber_factory=lambda:transcriber,text_provider_factory=factory)
    db=service.create_copy(source.name,'PAT-001')
    return service,db,provider,factory,transcriber,source


def execute(service,db,**kwargs):
    return service.process(db,'PAT-001','A03',datetime.now(timezone.utc),**kwargs)


def test_disabled_text_never_creates_provider(text_workspace):
    s,db,p,f,t,source=text_workspace;before=source.read_bytes()
    r=execute(s,db);assert r.persisted
    assert s.reader.detail(db,UUID(r.session_id)).document['documents'][0]['evidence']['llm']['status']=='disabled'
    f.assert_not_called();p.generate.assert_not_called();assert source.read_bytes()==before


def test_cloud_requires_authorization_before_asr(text_workspace):
    s,db,p,f,t,_=text_workspace
    with pytest.raises(HistoryError,match='cloud_text_authorization_required'):execute(s,db,llm_enabled=True)
    f.assert_not_called();t.transcribe_with_details.assert_not_called()


def test_valid_prompt_revision_result_reopen_and_no_alert_decision(text_workspace):
    s,db,p,f,t,source=text_workspace;before=source.read_bytes()
    off=execute(s,db)
    enabled=execute(s,db,llm_enabled=True,cloud_text_authorized=True)
    assert enabled.persisted and enabled.status=='completed'
    d=s.reader.detail(db,UUID(enabled.session_id)).document;doc=d['documents'][0]['evidence'];llm=doc['llm']
    assert llm['prompt_sha256']==PROMPT_SHA256 and llm['prompt_revision']=='text-v3-prompt-v2'
    assert llm['result']['sentiment']=='neutral' and llm['provider']['is_mock'] is True
    assert llm['result']['input_sha256']==doc['asr']['input_text_sha256']
    p.generate.assert_called_once_with(system_prompt=PROMPT_V2,text='Não senti dor.')
    previous=s.reader.detail(db,UUID(off.session_id)).document['documents'][0]['evidence']
    assert previous['rules']==doc['rules'] and len(d['events'])==2
    assert all(r['event']['review_status']=='pending_review' for r in d['events'])
    assert source.read_bytes()==before
    from medassistmultimodal.desktop_text import optional_audio_text
    assert 'Sentimento textual: Neutro' in optional_audio_text(s.reader.detail(db,UUID(enabled.session_id)))


@pytest.mark.parametrize('mode,expected',[('timeout','timeout'),('unavailable','unavailable'),('invalid','invalid_response')])
def test_text_failure_preserves_rules_and_transcript_without_retry(text_workspace,mode,expected):
    s,db,p,f,t,_=text_workspace
    if mode=='timeout':p.generate.side_effect=LLMProviderTimeoutError('PRIVATE_SECRET')
    elif mode=='unavailable':p.generate.side_effect=LLMProviderUnavailableError('PRIVATE_SECRET')
    else:p.generate.return_value='invalid JSON'
    r=execute(s,db,llm_enabled=True,cloud_text_authorized=True);assert r.persisted and r.status=='degraded'
    d=s.reader.detail(db,UUID(r.session_id)).document['documents'][0]['evidence']
    assert d['llm']['status']==expected and d['asr']['result']['text']=='Não senti dor.'
    assert len(d['rules']['items'])==1 and d['llm']['final_content'] is None
    assert 'PRIVATE_SECRET' not in json.dumps(d);p.generate.assert_called_once()


def test_persistence_retry_does_not_repeat_providers(text_workspace):
    s,db,p,f,t,_=text_workspace
    with patch('medassistmultimodal.infrastructure.desktop_text.register_audio_sqlite',side_effect=sqlite3.OperationalError('test-only')):
        r=execute(s,db,llm_enabled=True,cloud_text_authorized=True)
    assert not r.persisted
    assert s.retry_persistence(db,r.run_id).persisted
    assert s.retry_persistence(db,r.run_id).persisted
    p.generate.assert_called_once();t.transcribe_with_details.assert_called_once()
    assert len(s.reader.sessions(db,'PAT-001'))==2


def test_capacity_limit_preserves_rules_without_cloud_call(text_workspace):
    s,db,p,f,t,_=text_workspace;run=t.transcribe_with_details.return_value
    t.transcribe_with_details.return_value=replace(run,transcript=replace(run.transcript,text=' '.join(['dor']*9)))
    r=execute(s,db,llm_enabled=True,cloud_text_authorized=True)
    doc=s.reader.detail(db,UUID(r.session_id)).document['documents'][0]['evidence']
    assert doc['llm']['status']=='unsupported_input' and len(doc['rules']['items'])==9
    p.generate.assert_not_called()


def test_prompt_bridge_and_stored_analysis_are_validated(text_workspace):
    s,db,p,_,_,_=text_workspace
    with pytest.raises(ValueError):PromptV2Bridge(p).generate(system_prompt='other prompt',text='Não senti dor.')
    r=execute(s,db,llm_enabled=True,cloud_text_authorized=True)
    doc=s.reader.detail(db,UUID(r.session_id)).document['documents'][0]['evidence']
    doc['llm']['result']['sentiment']='positive'
    with pytest.raises(ValueError):validate_optional_text(doc)


def check_tk_optional_text_default_confirmation_and_render(tmp_path,text_workspace,tk_runtime):
    from tests.unit.test_desktop_workflow import pump
    from medassistmultimodal.desktop_text import TextAudioApp
    s,db,p,f,t,_=text_workspace;root=tk.Toplevel(tk_runtime);root.withdraw()
    app=TextAudioApp(root,reader=s.reader,workspace=s,project_root=tmp_path)
    try:
        assert app.use_cloud_text.get() is False
        app.database.set(db);app.load_history();pump(root,app);app.case.set('A03')
        app.use_cloud_text.set(True)
        with patch('medassistmultimodal.desktop_text.messagebox.askyesno',return_value=False):app.process_audio()
        f.assert_not_called();t.transcribe_with_details.assert_not_called()
        with patch('medassistmultimodal.desktop_text.messagebox.askyesno',return_value=True):app.process_audio()
        assert str(app.cloud_check.cget('state'))=='disabled';pump(root,app)
        assert str(app.cloud_check.cget('state'))=='normal'
        new=next(row for row in app.state.rows if s.reader.detail(db,UUID(row.session_id)).document['documents'][0]['evidence']['llm']['status']=='succeeded')
        app.sessions.selection_set(new.session_id);app.select_session();pump(root,app)
        assert 'Sentimento textual: Neutro' in app.audio.get('1.0','end')
        assert app.state.detail.document['documents'][0]['evidence']['llm']['prompt_revision']=='text-v3-prompt-v2'
        app.patient.set('PAT-999')
        with patch('medassistmultimodal.desktop_text.messagebox.askyesno') as confirm:app.process_audio()
        confirm.assert_not_called()
        app.database.set('missing.sqlite3');app.load_history();pump(root,app)
        assert app.state.detail is None and 'Sentimento textual:' not in app.audio.get('1.0','end')
    finally:
        if app.worker.busy:app.worker.thread.join(3);app.worker.drain()
        root.after_cancel(app.poll_id);root.destroy()
