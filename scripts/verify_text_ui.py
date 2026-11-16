"""One authorized fictional A03 audio run with optional GPT-OSS; no retry or review."""
from medassistmultimodal.desktop_text import TextAudioApp,TextWorkspace,TextHistoryReader
from medassistmultimodal.infrastructure.desktop_text import PROMPT_SHA256
from medassistmultimodal.application.register_vitals import strict_json,encode_json
from pathlib import Path
from datetime import datetime,timezone
from uuid import UUID
import hashlib
import time
import tkinter as tk

ROOT=Path(__file__).resolve().parents[1]


def main():
    source='data/interim/audio/desktop_workspaces_v1/f704d423-6888-4084-9615-eb04a6bc6fbd/audio.sqlite3'
    output=ROOT/'data/interim/audio/text_ui_gpt_oss_v1';output.mkdir(exist_ok=False)
    reader=TextHistoryReader(ROOT);references={source}
    for row in reader.sessions(source,'PAT-001'):
        d=reader.detail(source,UUID(row.session_id)).document
        for area in ('documents','vitals','prescriptions'):references.update(x['reference'] for x in d[area])
    before={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sorted(references)}
    code=['src/medassistmultimodal/infrastructure/desktop_text.py','src/medassistmultimodal/desktop_text.py',
        'src/medassistmultimodal/providers/ollama_text_v3_prompt_v2.py','scripts/verify_text_ui.py']
    (output/'config.json').write_bytes(encode_json(dict(date='2026-11-10',case='A03',model='gpt-oss:120b-cloud',
        prompt_revision='text-v3-prompt-v2',prompt_sha256=PROMPT_SHA256,temperature=0,think='low',max_tokens=1536,timeout_seconds=60,
        planned_asr_calls=1,planned_cloud_calls_maximum=1,retries=0,source=source,original_sha256=before,
        code_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in code})))
    root=tk.Tk();root.withdraw();workspace=TextWorkspace(ROOT)
    app=TextAudioApp(root,reader=workspace.reader,workspace=workspace,project_root=ROOT)
    ticks=[];results=[]
    def beat():ticks.append(time.monotonic());root.after(15,beat)
    root.after(15,beat)
    def pump():
        deadline=time.monotonic()+150
        while app.worker.busy:
            root.update();time.sleep(.005)
            if time.monotonic()>deadline:raise RuntimeError('Verification deadline exceeded')
        root.update()
    try:
        database=workspace.create_copy(source,'PAT-001')
        app.database.set(database);app.load_history();pump()
        started=time.monotonic();start_ticks=len(ticks)
        app.dispatch(lambda progress:workspace.process(database,'PAT-001','A03',datetime.now(timezone.utc),progress,
            llm_enabled=True,cloud_text_authorized=True),results.append,'Conferência autorizada Whisper/GPT-OSS…')
        pump();assert len(results)==1,app.status.get()
        result=results[0];assert result.persisted
        app.load_history();pump()
        app.sessions.selection_set(result.session_id);app.select_session();pump()
        detail=app.state.detail.document;doc=detail['documents'][0]['evidence'];llm=doc['llm']
        assert llm['provider']['source']=='ollama_cloud' and llm['provider']['is_mock'] is False
        assert all(r['event']['review_status']=='pending_review' for r in detail['events'])
        assert doc['asr']['provider']['is_mock'] is False
        if llm['status']=='succeeded':assert 'Sentimento textual:' in app.audio.get('1.0','end')
        assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==sha for p,sha in before.items())
        assert TextHistoryReader(ROOT).detail(database,UUID(result.session_id)).document==detail
        (output/'export.json').write_bytes(encode_json(detail))
        summary=dict(date='2026-11-10',database=database,session_id=result.session_id,run_id=result.run_id,
            status=result.status,llm_status=llm['status'],asr_status=doc['asr']['status'],rules_status=doc['rules']['status'],
            input_text_sha256=doc['asr']['input_text_sha256'],llm_result=llm['result'],model=llm['provider']['model'],
            response_metadata=llm.get('response_metadata'),event_count=len(detail['events']),all_new_events_pending=True,
            original_files_unchanged=True,tk_heartbeats=len(ticks)-start_ticks,elapsed_seconds=time.monotonic()-started,
            planned_calls_executed_once=True,automatic_reviews=0,clinical_validation=False,visual_inspection=False)
        (output/'summary.json').write_bytes(encode_json(summary));print(encode_json(summary).decode('utf-8'))
    finally:
        if app.worker.busy:app.worker.thread.join()
        root.after_cancel(app.poll_id);root.destroy()


if __name__=='__main__':main()
