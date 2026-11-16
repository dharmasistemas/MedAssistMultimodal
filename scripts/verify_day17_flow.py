"""Bounded day-17 closeout: existing evidence, readonly export, Tk reopen, mock-only review."""
from medassistmultimodal.desktop_multimodal import MultimodalApp  # Native environment first.
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import argparse
import hashlib
import gc
from pathlib import Path
import sqlite3
import time
import tkinter as tk
from uuid import UUID, uuid4

from medassistmultimodal.application.desktop_history import HistoryError
from medassistmultimodal.application.register_vitals import encode_json, strict_json
from medassistmultimodal.application.review_event import EventReviewRequest
from medassistmultimodal.domain.events import ReviewStatus
from medassistmultimodal.infrastructure.desktop_vitals import MultimodalHistoryReader
from medassistmultimodal.infrastructure.structured_workspace import StructuredWorkspace
from medassistmultimodal.providers.whisper_local import checked_path

ROOT=Path(__file__).resolve().parents[1]
SOURCE='data/interim/audio/desktop_workspaces_v1/8d8ce8d6-ef81-47f6-a647-7cdb41f57b07/audio.sqlite3'
OUTPUT='data/interim/multimodal/day17_closeout_v1'


def collect_export(root,database,patient_id='PAT-001'):
    """No models or writes. Reject a changing DB rather than export a mixed revision."""
    root=Path(root).absolute();reader=MultimodalHistoryReader(root)
    rows=reader.sessions(database,patient_id)  # Validate path/schema/patient first.
    path=checked_path(database,root)
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=2)) as monitor:
        monitor.execute('PRAGMA query_only=ON')
        version=monitor.execute('PRAGMA data_version').fetchone()[0]
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        rows=reader.sessions(database,patient_id)
        sessions=[reader.detail(database,UUID(row.session_id)).document for row in rows]
        if any(s['unsupported_sources'] for s in sessions):raise HistoryError('evidence_unsupported')
        after=monitor.execute('PRAGMA data_version').fetchone()[0]
        if version!=after or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise HistoryError('export_conflict')
    events=[r for s in sessions for r in s['events']]
    return dict(schema_version='multimodal-technical-export-v1',database=path.relative_to(root).as_posix(),
        database_sha256=digest,patient_id=patient_id,sessions=sessions,
        summary=dict(sessions=len(sessions),events=len(events),
            events_by_modality=dict(Counter(r['modality'] for r in events)),
            review_status=dict(Counter(r['event']['review_status'] for r in events)),
            review_audits=sum(len(h) for s in sessions for h in s['review_histories'].values())),
        clinical_validation=False,clinical_report=False,temporal_alignment_validated=False,
        causal_correlation_validated=False,access_mode='read_only',
        note='Fictional patient; separate sessions and nominal times. Evidence integrity is not clinical validation.')


def referenced_hashes(root,export):
    references={export['database']}
    for session in export['sessions']:
        for area in ('documents','vitals','prescriptions'):
            references.update(d['reference'] for d in session[area])
    return {r:hashlib.sha256(checked_path(r,root).read_bytes()).hexdigest() for r in sorted(references)}


def verify_widgets(root_path,database,expected):
    """Functional widget checks, not a visual inspection. No dialog confirmation or review."""
    runtime=tk.Tk();runtime.withdraw();checked=[];apps=[]
    try:
        # Destroy and reconstruct the app, forcing fresh readers/connections and widgets.
        for cycle in range(2):
            window=tk.Toplevel(runtime);window.withdraw()
            service=StructuredWorkspace(root_path)
            app=MultimodalApp(window,reader=service.reader,workspace=service,project_root=root_path)
            apps.append(app)  # Keep Tcl variables reachable while another worker can trigger GC.
            def pump():
                deadline=time.monotonic()+15
                while app.worker.busy:
                    runtime.update();time.sleep(.005)
                    if time.monotonic()>deadline:raise RuntimeError('Tk check exceeded deadline')
                runtime.update()
                if app.state.status=='error':raise RuntimeError(app.state.error_code)
            try:
                app.database.set(database);app.load_history();pump()
                assert len(app.sessions.get_children())==len(expected['sessions'])
                for document in expected['sessions']:
                    sid=document['session']['session_id'];app.sessions.selection_set(sid);app.select_session();pump()
                    assert app.state.detail.document==document
                    assert len(app.events.get_children())==len(document['events'])
                    if document['vitals']:assert app.samples.get_children()
                    if document['prescriptions']:assert app.prescription_items.get_children()
                    checked.append(dict(reopen_cycle=cycle,session_id=sid,events=len(document['events'])))
                # Failure clears the previous verified detail rather than presenting stale data.
                app.database.set('data/interim/multimodal/missing-day17.sqlite3');app.load_history()
                deadline=time.monotonic()+15
                while app.worker.busy:
                    runtime.update();time.sleep(.005)
                    if time.monotonic()>deadline:raise RuntimeError('Tk error check exceeded deadline')
                assert app.state.status=='error' and app.state.detail is None
                assert not app.events.get_children() and not app.samples.get_children() and not app.prescription_items.get_children()
            finally:
                if app.worker.busy:app.worker.thread.join(15)
                assert not app.worker.busy
                window.after_cancel(app.poll_id);window.destroy()
    finally:
        # Reclaim widget cycles on their owner thread before disposing the Tcl interpreter.
        apps.clear()
        if "app" in locals():del app
        gc.collect()
        runtime.destroy()
    return checked


def run(root,source=SOURCE,output=OUTPUT):
    root=Path(root).absolute();destination=checked_path(output,root)
    if not destination.is_relative_to(root/'data/interim/multimodal'):raise ValueError('Unsupported output area')
    before_export=collect_export(root,source)
    originals=referenced_hashes(root,before_export)
    destination.mkdir(parents=True,exist_ok=False)
    code=['scripts/verify_day17_flow.py','src/medassistmultimodal/desktop_multimodal.py',
        'src/medassistmultimodal/infrastructure/structured_workspace.py','src/medassistmultimodal/infrastructure/desktop_vitals.py',
        'src/medassistmultimodal/infrastructure/desktop_prescriptions.py']
    (destination/'config.json').write_bytes(encode_json(dict(date='2026-11-08',source=source,
        original_sha256=originals,code_sha256={n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in code},
        model_calls_planned=0,review_scope='technical_simulation; copied mock event only')))
    workspace=StructuredWorkspace(root);database=workspace.create_copy(source,'PAT-001')
    initial=collect_export(root,database)
    event=None;session=None
    for candidate in initial['sessions']:
        for row in candidate['events']:
            if row['event']['is_mock'] and row['event']['review_status']=='pending_review':
                event=row['event'];session=UUID(candidate['session']['session_id']);break
        if event:break
    if event is None:raise RuntimeError('No pending mock event available; no automated human review allowed')
    request=EventReviewRequest(review_id=uuid4(),event_id=UUID(event['event_id']),
        reviewer_ref='technical-day17-fixture',reviewed_at=datetime.now(timezone.utc),
        reason='Automated technical closeout on copied mock evidence only; no clinical validation.',
        target_status=ReviewStatus.REVIEWED,scope='technical_simulation')
    audit=workspace.review(database,session,request,event['evidence_ref'])
    first=collect_export(root,database)
    assert workspace.review(database,session,request,event['evidence_ref'])==audit
    exported=collect_export(root,database);assert exported==first
    assert set(exported['summary']['events_by_modality'])=={'audio','vitals','prescriptions'}
    # A fresh service after re-opening must return exactly the same events and audits.
    assert collect_export(root,database)==exported
    checks=verify_widgets(root,database,exported)
    assert collect_export(root,database)==exported
    assert all(hashlib.sha256(checked_path(ref,root).read_bytes()).hexdigest()==sha for ref,sha in originals.items())
    raw=encode_json(exported);(destination/'export.json').write_bytes(raw)
    assert strict_json((destination/'export.json').read_bytes())==exported
    summary=dict(date='2026-11-08',database=database,**exported['summary'],
        models_executed=0,original_files_unchanged=True,review_replay_without_duplication=True,
        technical_review=dict(event_id=event['event_id'],audit_id=audit,scope='technical_simulation',
            reviewer_ref='technical-day17-fixture',is_mock=True),
        user_review_created=False,clinical_validation=False,visual_inspection=False,
        widget_reopen_cycles=2,widget_sessions_checked=len(checks),failure_clears_details=True,
        export_sha256=hashlib.sha256(raw).hexdigest())
    (destination/'widget_checks.json').write_bytes(encode_json(checks))
    (destination/'summary.json').write_bytes(encode_json(summary))
    print(encode_json(summary).decode('utf-8'))
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',default=SOURCE);parser.add_argument('--output',default=OUTPUT)
    args=parser.parse_args();run(ROOT,args.source,args.output)


if __name__=='__main__':main()
