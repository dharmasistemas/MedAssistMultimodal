"""Check saved real RGB evidence through Tk and a preview; no new pose inference or review."""
from medassistmultimodal.desktop_video import VideoApp,VideoWorkspace,VideoHistoryReader
from medassistmultimodal.application.register_vitals import strict_json,encode_json
from pathlib import Path
import hashlib
import time
import tkinter as tk
from uuid import UUID

ROOT=Path(__file__).resolve().parents[1]


def main():
    output=ROOT/'data/interim/rehab26/video_ui_v2'
    target=output/'ui_checks.json'
    if target.exists():raise ValueError('Verification output already exists')
    summary=strict_json((output/'summary.json').read_bytes());database=summary['database'];sid=summary['session_id']
    source=ROOT/'data/interim/audio/desktop_workspaces_v1/ee528c58-47e3-4ede-9992-fe44a4cebefd/audio.sqlite3'
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    root=tk.Tk();root.withdraw();workspace=VideoWorkspace(ROOT)
    app=VideoApp(root,reader=workspace.reader,workspace=workspace,project_root=ROOT)
    ticks=[]
    def beat():ticks.append(time.monotonic());root.after(15,beat)
    root.after(15,beat)
    def pump():
        deadline=time.monotonic()+30
        while app.worker.busy:
            root.update();time.sleep(.005)
            if time.monotonic()>deadline:raise RuntimeError('UI check exceeded deadline')
        root.update()
    try:
        app.database.set(database);app.load_history();pump()
        assert len(app.sessions.get_children())==6  # Dataset session is absent from PAT-001.
        app.load_video_history();pump();assert sid in app.video_ids
        app.video_session.set(sid);app.select_video();pump()
        assert app.video_active and len(app.video_samples.get_children())==80
        assert len(app.events.get_children())==2
        assert all(r['event']['review_status']=='pending_review' for r in app.state.detail.document['events'])
        app.video_samples.selection_set(app.video_samples.get_children()[0]);root.update();pump();assert app.preview_image is not None
        app.export_video();pump();assert 'Exportação técnica' in app.status.get()
        reference=app.status.get().split(': ',1)[1]
        exported=strict_json((ROOT/reference).read_bytes())
        assert exported==VideoHistoryReader(ROOT).detail(database,UUID(sid)).document
        assert exported['session']['patient_id'] is None
        assert hashlib.sha256(source.read_bytes()).hexdigest()==before
        target.write_bytes(encode_json(dict(database=database,session_id=sid,patient_sessions=6,dataset_sessions=len(app.video_ids),
            timeline_rows=80,events=2,real_frame_displayed=True,export_ref=reference,export_matches_reopened_session=True,
            original_database_unchanged=True,tk_heartbeats=len(ticks),automated_reviews=0,new_pose_inferences=0,
            visual_inspection=False)))
        print(target.relative_to(ROOT).as_posix())
    finally:
        if app.worker.busy:app.worker.thread.join(30)
        root.after_cancel(app.poll_id);root.destroy()


if __name__=='__main__':main()
