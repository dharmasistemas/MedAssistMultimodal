from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
import json

import pytest

from medassistmultimodal.application.desktop_history import HistoryError
from medassistmultimodal.infrastructure.desktop_video import ELBOW_CASES,validate_interval
from tests.unit.test_desktop_video import video_db
from tests.unit.test_structured_workspace import structured


@pytest.mark.parametrize('case,first,last',[('D9-04',897,1056),('D9-10',14599,14690),(None,0,449)])
def test_allowed_case_interval(case,first,last):
    validate_interval(first,last,case)


@pytest.mark.parametrize('case,first,last',[
    ('unknown',897,1056),('D9-04',897,1055),(None,897,1056),('D9-04',True,1056)])
def test_invalid_case_does_not_start_assets(video_db,case,first,last):
    s,db,_,_=video_db
    with patch('medassistmultimodal.infrastructure.desktop_video.assets') as read:
        with pytest.raises(HistoryError):s.process_video(db,first,last,case_id=case)
    read.assert_not_called()


def test_mock_extractor_extended_interval_v2_and_persistence(video_db,tmp_path):
    s,db,_,_=video_db
    for name in ('clip.mp4','pose.task'):(tmp_path/name).write_bytes(b'fixture')
    manifest=dict(video=dict(path='clip.mp4',sha256='a'*64,participant_ref='P-0236ac1b114742088a082d0b6163bae1',group='development'),
        model=dict(path='pose.task',sha256='b'*64))
    first,last=ELBOW_CASES['D9-04']
    reader=SimpleNamespace(info=SimpleNamespace(fps=30,declared_frames=15149),
        frames=lambda a,b:(SimpleNamespace(index=i) for i in range(a,b+1)))
    detector=SimpleNamespace(detect=lambda f:f)
    row=dict(measurements={n:dict(degrees=140.,reason=None) for n in ('right_elbow','right_arm_trunk')},
        visibility={str(i):1. for i in (12,14,16,24)})
    with patch('medassistmultimodal.infrastructure.desktop_video.assets',return_value=manifest), \
         patch('medassistmultimodal.infrastructure.desktop_video.VideoReader',return_value=nullcontext(reader)), \
         patch('medassistmultimodal.infrastructure.desktop_video.MediaPipePose',return_value=nullcontext(detector)), \
         patch('medassistmultimodal.infrastructure.desktop_video.inspect_pose',return_value=row), \
         patch('medassistmultimodal.infrastructure.desktop_video.digest',side_effect=lambda p:'a'*64 if p.name=='clip.mp4' else 'b'*64), \
         patch('medassistmultimodal.infrastructure.desktop_video.importlib.metadata.version',return_value='fixture'), \
         patch.object(s,'_persist_video'):
        outcome=s.process_video(db,first,last,case_id='D9-04')
    prepared=s.video_prepared[outcome.run_id][1];doc=json.loads(prepared.evidence)
    assert outcome.persisted and doc['schema_version']=='rgb-video-evidence-v2'
    assert doc['elbow_analysis']['status']=='deviation'
    assert doc['source']['case_id']=='D9-04' and len(doc['original_frames'])==160
    # Injected providers above are fixtures, never persisted as real evidence.


def check_tk_elbow_case_selection_and_render(tmp_path,video_db,tk_runtime):
    import tkinter as tk
    from tests.unit.test_elbow_deviation import prepare_v2
    from tests.unit.test_desktop_workflow import pump
    from medassistmultimodal.desktop_video import VideoApp
    s,db,old,_=video_db
    ref=(s.writable_path(db).parent/f'v2_{uuid4()}.json').relative_to(tmp_path).as_posix()
    prepared=prepare_v2(old,ref,[140.]*5);s._persist_video(db,prepared)
    root=tk.Toplevel(tk_runtime);root.withdraw()
    app=VideoApp(root,reader=s.reader,workspace=s,project_root=tmp_path)
    try:
        app.database.set(db);app.load_history();pump(root,app)
        app.video_case.set('D9-04');app.choose_video_case()
        assert (app.video_first.get(),app.video_last.get())==('897','1056')
        with patch('medassistmultimodal.desktop_video.messagebox.askyesno',return_value=False) as confirm:
            app.process_video()
        assert '897' in confirm.call_args.args[1]
        app.video_last.set('1055')
        with patch('medassistmultimodal.desktop_video.messagebox.askyesno') as confirm:app.process_video()
        confirm.assert_not_called()
        app.load_video_history();pump(root,app)
        app.video_session.set(str(prepared.session.session_id));app.select_video();pump(root,app)
        assert 'Sinal experimental de flexão' in app.video_summary.get('1.0','end')
        assert any('Desvio experimental' in str(app.events.item(i,'values')) for i in app.events.get_children())
        with patch.object(s,'preview',return_value=b'P6\n1 1\n255\n\xff\x00\x00') as preview:
            app.video_samples.selection_set('frame-897');root.update();pump(root,app)
        preview.assert_called_with(897)
        assert app.preview_image is not None
    finally:
        if app.worker.busy:app.worker.thread.join(3);app.worker.drain()
        root.after_cancel(app.poll_id);root.destroy()
