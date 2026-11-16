"""Read saved evaluation through Tk and render one real frame; no pose or review."""
from pathlib import Path
from uuid import UUID
import time
import tkinter as tk

from medassistmultimodal.desktop_video import VideoApp,VideoWorkspace
from medassistmultimodal.application.register_vitals import strict_json,encode_json
from medassistmultimodal.infrastructure.desktop_video import digest

ROOT=Path(__file__).resolve().parents[1]


def main():
    output=ROOT/'data/interim/rehab26/elbow_rgb_v1'
    target=output/'ui_checks.json'
    if target.exists():raise ValueError('Exclusive verification output already exists')
    summary=strict_json((output/'summary.json').read_bytes());database=summary['database']
    case=strict_json((output/'D9-04.json').read_bytes());sid=case['session_id']
    before=digest(ROOT/database)
    workspace=VideoWorkspace(ROOT);root=tk.Tk();root.withdraw()
    app=VideoApp(root,reader=workspace.reader,workspace=workspace,project_root=ROOT)
    def pump():
        deadline=time.monotonic()+90
        while app.worker.busy or app.preview_after is not None:
            root.update();time.sleep(.01)
            if time.monotonic()>deadline:raise RuntimeError('UI operation exceeded deadline')
        root.update()
    try:
        app.database.set(database);app.load_history();pump()
        app.video_case.set('D9-04');app.choose_video_case()
        assert (app.video_first.get(),app.video_last.get())==('897','1056')
        app.load_video_history();pump();assert sid in app.video_ids
        app.video_session.set(sid);app.select_video();pump()
        assert app.video_active and len(app.video_samples.get_children())==160
        assert 'Sinal experimental de flexão' in app.video_summary.get('1.0','end')
        assert sum('Desvio experimental' in str(app.events.item(i,'values')) for i in app.events.get_children())==1
        app.video_samples.selection_set('frame-897');root.update();pump()
        assert app.preview_image is not None
        app.export_video();pump();reference=app.status.get().split(': ',1)[1]
        assert strict_json((ROOT/reference).read_bytes())==workspace.reader.detail(database,UUID(sid)).document
        assert before==digest(ROOT/database)
        with target.open('xb') as f:f.write(encode_json(dict(database=database,session_id=sid,
            frame=897,frame_rendered=True,timeline_rows=160,candidate_rows=1,
            database_unchanged=True,export_reference=reference,visual_inspection=False,
            pose_inferences=0,automated_reviews=0)))
        print(target.relative_to(ROOT).as_posix())
    finally:
        if app.worker.busy:app.worker.thread.join(90);app.worker.drain()
        root.after_cancel(app.poll_id);root.destroy()


if __name__=='__main__':main()
