"""Bounded integration: one real local A08 ASR; technical review on a copied mock event."""
from medassistmultimodal.desktop_workflow import WorkflowApp  # Native environment first.
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import time
import tkinter as tk
from uuid import UUID, uuid4

from medassistmultimodal.application.register_vitals import encode_json, strict_json
from medassistmultimodal.application.review_event import EventReviewRequest
from medassistmultimodal.domain.events import ReviewStatus
from medassistmultimodal.infrastructure.desktop_history import SQLiteHistoryReader
from medassistmultimodal.infrastructure.desktop_workspace import DesktopWorkspace

ROOT=Path(__file__).resolve().parents[1]


def main():
    source='data/interim/audio/day15_real_flow_v1/audio.sqlite3'
    originals=[p for p in (ROOT/source).parent.iterdir() if p.is_file() and p.suffix in ('.sqlite3','.json')]
    before={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in originals}
    output=ROOT/'data/interim/audio/day16_worker_flow_v1';output.mkdir(exist_ok=False)
    code=['scripts/verify_day16_worker.py','src/medassistmultimodal/desktop_workflow.py',
          'src/medassistmultimodal/application/desktop_worker.py','src/medassistmultimodal/infrastructure/desktop_workspace.py']
    config=dict(date='2026-11-07',case='A08',real_whisper_calls_planned=1,cloud_calls=0,
        technical_review_only=True,clinical_review=False,source=source,original_sha256=before,
        code_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in code})
    (output/'config.json').write_bytes(encode_json(config))
    root=tk.Tk();root.withdraw();reader=SQLiteHistoryReader(ROOT);workspace=DesktopWorkspace(ROOT)
    app=WorkflowApp(root,reader=reader,workspace=workspace,project_root=ROOT)
    ticks=[];results=[]
    def beat():
        ticks.append(time.monotonic());root.after(15,beat)
    root.after(15,beat)
    def pump():
        deadline=time.monotonic()+180
        while app.worker.busy:
            root.update();time.sleep(.005)
            if time.monotonic()>deadline:raise RuntimeError('Integration verification exceeded deadline')
        root.update()
        assert results,app.status.get()
        return results.pop()
    try:
        app.dispatch(lambda progress:workspace.create_copy(source,'PAT-001'),results.append,'copy')
        database=pump()
        start_ticks=len(ticks);started=time.monotonic()
        app.dispatch(lambda progress:workspace.process(database,'PAT-001','A08',
            datetime(2026,11,7,12,tzinfo=timezone.utc),progress),results.append,'local ASR')
        result=pump();duration=time.monotonic()-started
        assert result.persisted and result.status=='completed'
        processed=reader.detail(database,UUID(result.session_id)).document
        evidence=processed['documents'][0]['evidence']
        assert evidence['asr']['provider']['is_mock'] is False and evidence['llm']['status']=='disabled'
        assert all(r['event']['review_status']=='pending_review' for r in processed['events'])
        heartbeat_count=len(ticks)-start_ticks;assert heartbeat_count>1
        # Explicitly simulated technical review, never attributed to the project user.
        fixture=None
        for row in reader.sessions(database,'PAT-001'):
            detail=reader.detail(database,UUID(row.session_id)).document
            if detail['documents'][0]['evidence']['asr']['provider']['is_mock']:
                fixture=detail;break
        event=next(r['event'] for r in fixture['events'] if r['event']['review_status']=='pending_review')
        request=EventReviewRequest(review_id=uuid4(),event_id=UUID(event['event_id']),
            reviewer_ref='technical-worker-fixture',reviewed_at=datetime.now(timezone.utc),
            reason='Automated technical simulation on copied mock evidence; no clinical validation.',
            target_status=ReviewStatus.REVIEWED,scope='technical_simulation')
        def review(progress):
            return workspace.review(database,UUID(fixture['session']['session_id']),request,event['evidence_ref'])
        app.dispatch(review,results.append,'technical review');audit_id=pump()
        app.dispatch(review,results.append,'replay same review');assert pump()==audit_id
        revised=reader.detail(database,UUID(fixture['session']['session_id'])).document
        assert len(revised['review_histories'][event['event_id']])==1
        after={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in originals}
        assert before==after
        (output/'export_new_session.json').write_bytes(encode_json(processed))
        (output/'export_technical_review.json').write_bytes(encode_json(revised))
        summary=dict(date='2026-11-07',workspace=database,real_whisper_calls=1,cloud_calls=0,
            processing_seconds=duration,tk_heartbeats_during_processing=heartbeat_count,
            result=dict(run_id=result.run_id,session_id=result.session_id,status=result.status),
            new_events=len(processed['events']),new_events_pending=True,technical_review_only=True,
            technical_audit_id=audit_id,review_replay_without_duplication=True,
            original_files_unchanged=True,clinical_validation=False)
        (output/'summary.json').write_bytes(encode_json(summary));print(encode_json(summary).decode())
    finally:
        if app.worker.busy:
            app.worker.thread.join()  # Do not abandon or kill a running provider/transaction.
        root.destroy()


if __name__=='__main__':main()
