from contextlib import closing
from datetime import datetime,timezone
import json
import math
import sqlite3
import tkinter as tk
from unittest.mock import patch
from uuid import UUID,uuid4

import pytest

from medassistmultimodal.application.register_video import prepare_video,restore_video
from medassistmultimodal.application.register_vitals import strict_json
from medassistmultimodal.application.desktop_history import HistoryError
from medassistmultimodal.domain.temporal_quality import OriginalFrame,OriginalAngle
from medassistmultimodal.domain.events import ReviewStatus
from medassistmultimodal.infrastructure.desktop_video import VideoWorkspace,VideoHistoryReader,PARTICIPANT
from tests.unit.test_structured_workspace import structured,request


def prepare_fixture(reference='data/interim/audio/desktop_workspaces_v1/fixture/video.json',*,missing=False):
    frames=[]
    values=[10]*3+[40]*3+[70]*15+[40]*3+[10]*3
    for i,v in enumerate(values):
        frames.append(OriginalFrame(i,OriginalAngle(None,'no_pose') if missing else OriginalAngle(170.),
            OriginalAngle(None,'no_pose') if missing else OriginalAngle(float(v)),
            tuple((n,None if missing else 1.) for n in (12,14,16,24))))
    source=dict(first_frame=0,last_frame=len(frames)-1,fps=30,group='development',dataset_id='rehab26-v1',participant_ref=PARTICIPANT,
        video_ref='data/raw/test.mp4',video_sha256='a'*64,model_sha256='b'*64,is_mock=True)
    return prepare_video(frames,source,run_id=uuid4(),processed_at=datetime.now(timezone.utc),evidence_ref=reference)


@pytest.fixture
def video_db(tmp_path,structured):
    _,db,source=structured;service=VideoWorkspace(tmp_path)
    ref=(service.writable_path(db).parent/'video_fixture.json').relative_to(tmp_path).as_posix()
    p=prepare_fixture(ref);service._persist_video(db,p);service.video_prepared[str(p.run_id)]=(str(service.writable_path(db)),p)
    return service,db,p,source


def test_video_cycle_evidence_roundtrip_and_dataset_identity():
    p=prepare_fixture();d=strict_json(p.evidence)
    assert d['summary']['detected_cycles']==1 and d['summary']['coverage']['right_arm_trunk']==1
    assert p.session.subject.patient_id is None and all(e.patient_id is None for e in p.events)
    assert d['clinical_validation'] is False and d['exercise_correctness_evaluated'] is False
    assert restore_video(d,p.events[0].evidence_ref.split('#')[0])==p


def test_no_pose_is_quality_not_normality():
    p=prepare_fixture(missing=True);d=strict_json(p.evidence)
    assert d['summary']['detected_cycles']==0 and d['summary']['coverage']['right_arm_trunk']==0
    assert len(d['quality_intervals'])==2 and len(p.events)==3
    assert all(row['right_elbow']['degrees'] is None for row in d['timeline'])


@pytest.mark.parametrize('field,value',[('first_frame',-1),('last_frame',450),('fps',29),('dataset_id','PAT-001'),('video_sha256','invalid')])
def test_invalid_source_rejected(field,value):
    p=prepare_fixture();d=strict_json(p.evidence);d['source'][field]=value
    with pytest.raises((ValueError,TypeError)):restore_video(d,p.events[0].evidence_ref.split('#')[0])


def test_reader_video_history_separate_from_patient_and_retry(tmp_path,video_db):
    s,db,p,source=video_db;before=source.read_bytes()
    assert s.reader.sessions(db,'PAT-001')==()
    assert len(s.reader.dataset_sessions(db))==1
    d=s.reader.detail(db,p.session.session_id).document
    assert d['integrity']=='verified' and d['session']['patient_id'] is None
    assert s.retry_video(db,str(p.run_id)).persisted and len(s.reader.dataset_sessions(db))==1
    assert source.read_bytes()==before


@pytest.mark.parametrize('failure',['missing','hash','event','group'])
def test_bad_video_evidence_blocks_detail_and_review(tmp_path,video_db,failure):
    s,db,p,_=video_db;file=tmp_path/p.events[0].evidence_ref.split('#')[0]
    if failure=='missing':file.rename(tmp_path/'saved.json')
    elif failure=='hash':file.write_bytes(b'changed')
    else:
        with closing(sqlite3.connect(tmp_path/db)) as c:
            if failure=='event':c.execute('UPDATE multimodal_events SET is_mock=0 WHERE event_id=?',(str(p.events[0].event_id),))
            else:c.execute('DELETE FROM multimodal_events WHERE event_id=?',(str(p.events[-1].event_id),))
            c.commit()
    with pytest.raises(HistoryError):s.reader.detail(db,p.session.session_id)
    with pytest.raises(HistoryError):s.review(db,p.session.session_id,request({'event_id':str(p.events[0].event_id)}),p.events[0].evidence_ref)


def test_video_review_replay_no_reset_and_evidence_unchanged(tmp_path,video_db):
    s,db,p,_=video_db;file=tmp_path/p.events[0].evidence_ref.split('#')[0];before=file.read_bytes()
    req=request({'event_id':str(p.events[-1].event_id)},scope='technical_simulation')
    audit=s.review(db,p.session.session_id,req,p.events[-1].evidence_ref)
    assert s.review(db,p.session.session_id,req,p.events[-1].evidence_ref)==audit
    assert len(s.reader.detail(db,p.session.session_id).document['review_histories'][str(req.event_id)])==1
    with pytest.raises(HistoryError,match='registration_conflict'):s.retry_video(db,str(p.run_id))
    assert file.read_bytes()==before


def test_video_persistence_failure_and_exclusive_evidence(tmp_path,video_db):
    s,db,p,source=video_db
    with pytest.raises(HistoryError):s._persist_video(source.name,p)
    with pytest.raises(HistoryError):s.retry_video(db,str(uuid4()))
    file=tmp_path/p.events[0].evidence_ref.split('#')[0];file.write_bytes(b'preserve')
    with pytest.raises(HistoryError,match='evidence_conflict'):s._persist_video(db,p)
    assert file.read_bytes()==b'preserve'


@pytest.mark.parametrize('first,last',[(-1,2),(0,450),(12,3),(True,2)])
def test_invalid_interval_does_not_load_model(video_db,first,last):
    s,db,_,_=video_db
    with patch('medassistmultimodal.infrastructure.desktop_video.assets') as read:
        with pytest.raises(HistoryError,match='video_interval_invalid'):s.process_video(db,first,last)
    read.assert_not_called()


def check_tk_video_history_review_export_and_clear(tmp_path,video_db,tk_runtime):
    from tests.unit.test_desktop_workflow import pump
    from medassistmultimodal.desktop_video import VideoApp
    s,db,p,_=video_db;root=tk.Toplevel(tk_runtime);root.withdraw()
    app=VideoApp(root,reader=s.reader,workspace=s,project_root=tmp_path)
    try:
        app.database.set(db);app.load_history();pump(root,app)
        app.load_video_history();pump(root,app)
        assert str(p.session.session_id) in app.video_ids
        app.video_session.set(str(p.session.session_id));app.select_video();pump(root,app)
        assert app.video_active and len(app.video_samples.get_children())==27
        assert 'independente' in app.video_summary.get('1.0','end')
        event=app.events.get_children()[-1];app.events.selection_set(event);app.select_event()
        app.reviewer.set('unit-test-only');app.reason.set('Widget fixture only, no clinical validation')
        with patch('medassistmultimodal.desktop_workflow.messagebox.askyesno',return_value=True):app.submit_review(ReviewStatus.REVIEWED)
        pump(root,app);assert app.video_active
        app.retry_review();pump(root,app)
        assert len(s.reader.detail(db,p.session.session_id).document['review_histories'][event])==1
        app.export_video();pump(root,app)
        exports=list((tmp_path/db).parent.glob('video_export_*.json'));assert len(exports)==1
        assert json.loads(exports[0].read_bytes())['session']['patient_id'] is None
        with patch.object(s,'preview',return_value=b'P6\n1 1\n255\n\xff\x00\x00'):
            app.video_samples.selection_set(app.video_samples.get_children()[0]);root.update();pump(root,app)
        assert app.preview_image is not None
        app.database.set('missing.sqlite3');app.load_history();pump(root,app)
        assert app.state.detail is None and not app.video_active and not app.video_samples.get_children() and not app.video_ids
    finally:
        if app.worker.busy:app.worker.thread.join(3);app.worker.drain()
        root.after_cancel(app.poll_id);root.destroy()


def test_missing_assets_do_not_start_provider_or_write(video_db,tmp_path):
    s,db,_,_=video_db;before=(tmp_path/db).read_bytes()
    with patch('medassistmultimodal.infrastructure.desktop_video.MediaPipePose') as provider:
        with pytest.raises(HistoryError,match='video_assets_invalid'):s.process_video(db,0,10)
    provider.assert_not_called();assert (tmp_path/db).read_bytes()==before


def test_failed_registration_retries_prepared_bytes_without_extraction(tmp_path,video_db):
    s,db,_,_=video_db
    ref=(s.writable_path(db).parent/'video_retry.json').relative_to(tmp_path).as_posix()
    p=prepare_fixture(ref);s.video_prepared[str(p.run_id)]=(str(s.writable_path(db)),p)
    with patch('medassistmultimodal.infrastructure.desktop_video.RegisterMultimodalSession.execute',side_effect=sqlite3.OperationalError('test-only')):
        with pytest.raises(sqlite3.OperationalError):s._persist_video(db,p)
    file=tmp_path/ref;before=file.read_bytes()
    with patch('medassistmultimodal.infrastructure.desktop_video.MediaPipePose') as provider:
        assert s.retry_video(db,str(p.run_id)).persisted
    provider.assert_not_called();assert file.read_bytes()==before
    assert len(s.reader.dataset_sessions(db))==2


def check_tk_video_preview_keeps_table_scrollable(tmp_path,video_db,tk_runtime,size,scaling):
    from tests.unit.test_desktop_workflow import pump
    from medassistmultimodal.desktop_video import VideoApp
    service,database,prepared,_=video_db
    original_scaling=float(tk_runtime.tk.call('tk','scaling'))
    tk_runtime.tk.call('tk','scaling',scaling)
    root=tk.Toplevel(tk_runtime);root.withdraw()
    app=VideoApp(root,reader=service.reader,workspace=service,project_root=tmp_path)
    try:
        root.geometry(size)
        app.database.set(database);app.load_history();pump(root,app)
        app.load_video_history();pump(root,app)
        app.video_session.set(str(prepared.session.session_id));app.select_video();pump(root,app)
        root.deiconify();root.update()
        # Reproduce a full-size portrait preview instead of the former one-pixel fixture.
        ppm=b'P6\n720 960\n255\n'+b'\x80\x80\x80'*(720*960)
        with patch.object(service,'preview',return_value=ppm):
            app.video_samples.selection_set(app.video_samples.get_children()[0]);root.update();pump(root,app)
        root.update()
        page=root.nametowidget(app.tabs.tabs()[1])
        assert app.video_samples.winfo_height()>=60
        assert app.video_samples.winfo_rooty()+app.video_samples.winfo_height()<=page.winfo_rooty()+page.winfo_height()
        assert app.video_scroll.winfo_ismapped()
        assert app.video_samples.winfo_rootx()>=app.preview_area.winfo_rootx()+app.preview_area.winfo_width()
        assert app.video_samples.winfo_rooty()>=app.video_summary.winfo_rooty()+app.video_summary.winfo_height()
        assert app.preview_area.winfo_height()>app.video_samples.winfo_height()
        available_height=min(app.preview_area.winfo_height()-4,
            (app.preview_area.winfo_width()-4)*app.preview_original.height/app.preview_original.width)
        assert app.preview_image.height()>=available_height-math.ceil(app.preview_original.height/16)-1
        assert app.preview_image.height()<=app.preview_area.winfo_height()
        assert app.preview_image.width()<=app.preview_area.winfo_width()
        # Invoke exactly the command wired to the vertical scrollbar.
        command=root.tk.splitlist(app.video_scroll.cget('command'))
        root.tk.call(*command,'moveto',1.0);root.update()
        assert app.video_samples.yview()[1]==1.0
        last=app.video_samples.get_children()[-1]
        assert app.video_samples.bbox(last)
        root.tk.call(*command,'moveto',0.0);root.update()
        assert app.video_samples.yview()[0]==0.0
        assert app.video_samples.bbox(app.video_samples.get_children()[0])
    finally:
        if app.worker.busy:app.worker.thread.join(3);app.worker.drain()
        root.after_cancel(app.poll_id);root.destroy()
        tk_runtime.tk.call('tk','scaling',original_scaling)


def check_tk_frame_selection_latest_wins_and_stale_clear(tmp_path,video_db,tk_runtime):
    from threading import Event
    import time
    from tests.unit.test_desktop_workflow import pump
    from medassistmultimodal.desktop_video import VideoApp
    service,database,prepared,_=video_db;root=tk.Toplevel(tk_runtime);root.withdraw()
    app=VideoApp(root,reader=service.reader,workspace=service,project_root=tmp_path)
    released=Event();calls=[]
    def settle():
        deadline=time.monotonic()+4
        while app.worker.busy or app.preview_after is not None:
            root.update();time.sleep(.005)
            if time.monotonic()>deadline:raise AssertionError('Preview queue did not settle')
        root.update()
    try:
        app.database.set(database);app.load_history();pump(root,app)
        app.load_video_history();pump(root,app)
        app.video_session.set(str(prepared.session.session_id));app.select_video();pump(root,app)
        def preview(index):
            calls.append(index)
            if index==0:assert released.wait(3)
            return b'P6\n1 1\n255\n\xff\x00\x00'
        rows=app.video_samples.get_children()
        with patch.object(service,'preview',side_effect=preview):
            app.video_samples.selection_set(rows[0]);root.update()
            assert app.worker.busy
            app.video_samples.selection_set(rows[1]);root.update()
            app.video_samples.selection_set(rows[-1]);root.update()
            released.set();settle()
        assert calls==[0,26]
        assert app.preview_caption.get().startswith('Frame 26 |') and app.preview_original is not None
        assert not hasattr(app,'preview_frame')  # No manual frame-number control.
        # An unavailable selected frame must clear the previous image.
        with patch.object(service,'preview',side_effect=HistoryError('video_assets_invalid')):
            app.video_samples.selection_set(rows[2]);root.update();settle()
        assert app.preview_original is None and app.preview_image is None
        assert 'indisponível' in app.preview_label.cget('text')
        released.clear()
        with patch.object(service,'preview',side_effect=preview):
            app.video_samples.selection_set(rows[0]);root.update();assert app.worker.busy
            app.state.begin();app.clear_details();released.set();settle()
        assert app.preview_original is None and app.preview_image is None and not app.video_active
    finally:
        released.set()
        if app.worker.busy:app.worker.thread.join(3);app.worker.drain()
        root.after_cancel(app.poll_id);root.destroy()


def test_preview_resampling_preserves_gradient_detail_and_source():
    from PIL import Image
    from medassistmultimodal.desktop_video import fit_preview_image
    source=Image.frombytes('RGB',(256,256),bytes(v for y in range(256) for x in range(256) for v in (x,x,x)))
    before=source.tobytes();resized=fit_preview_image(source,128,128)
    assert resized.size==(128,128)
    # Previous decimation by 16 retained only 16 column colors and enlarged blocks.
    assert len({resized.getpixel((x,64))[0] for x in range(128)})>100
    assert source.size==(256,256) and source.tobytes()==before
    assert fit_preview_image(source,512,512).size==(256,256)


def test_preview_resampling_keeps_portrait_aspect_and_fits_small_panel():
    from PIL import Image
    from medassistmultimodal.desktop_video import fit_preview_image
    image=Image.new('RGB',(540,960))
    assert fit_preview_image(image,300,480).size==(270,480)
    assert fit_preview_image(image,0,0).size==(1,1)
