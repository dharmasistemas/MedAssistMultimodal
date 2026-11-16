from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from threading import Event, get_ident
import time
import tkinter as tk
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from medassistmultimodal.application.desktop_history import HistoryError
from medassistmultimodal.application.desktop_worker import DesktopWorker
from medassistmultimodal.application.review_event import EventReviewRequest
from medassistmultimodal.domain.events import ReviewStatus
from medassistmultimodal.infrastructure.desktop_workspace import DesktopWorkspace, CORPUS
from medassistmultimodal.infrastructure.desktop_history import SQLiteHistoryReader
from tests.unit.test_desktop_history import persisted
from tests.unit.test_process_audio import fixture


def test_worker_busy_progress_result_and_thread_ownership():
    release=Event();worker=DesktopWorker();main=get_ident()
    def operation(progress):
        progress('processing');assert release.wait(2);return get_ident()
    worker.start(operation)
    try:
        assert worker.busy
        with pytest.raises(ValueError):worker.start(operation)
    finally:release.set()
    worker.thread.join(2)
    messages=worker.drain()
    assert [m.kind for m in messages]==['progress','done']
    assert messages[-1].value!=main and not worker.busy


@pytest.mark.parametrize('error,code',[(RuntimeError('PRIVATE_SECRET'),'operation_failed'),(HistoryError('audio_changed'),'audio_changed')])
def test_worker_errors_sanitized_without_retry(error,code):
    worker=DesktopWorker();calls=[]
    def operation(progress):calls.append(1);raise error
    worker.start(operation);worker.thread.join(2)
    messages=worker.drain()
    assert len(calls)==1 and messages[0].value==code and not worker.busy


def setup_workspace(tmp_path,persisted):
    source,p,store,_=persisted
    service=DesktopWorkspace(tmp_path)
    database=service.create_copy(source.name,'PAT-001')
    return source,p,store,service,database


def request_for(p):
    return EventReviewRequest(review_id=uuid4(),event_id=p.events[-1].event_id,reviewer_ref='test-fixture',
        reviewed_at=datetime.now(timezone.utc),reason='Explicit technical test',target_status=ReviewStatus.REVIEWED,
        scope='technical_simulation')


def test_copy_review_replay_and_source_evidence_preserved(tmp_path,persisted):
    source,p,store,service,database=setup_workspace(tmp_path,persisted)
    before=source.read_bytes(),store.read(p.evidence_ref)
    request=request_for(p)
    receipt=service.review(database,p.session.session_id,request,p.events[-1].evidence_ref)
    assert service.review(database,p.session.session_id,request,p.events[-1].evidence_ref)==receipt
    view=service.reader.detail(database,p.session.session_id).document
    assert len(view['review_histories'][str(request.event_id)])==1
    assert source.read_bytes()==before[0] and store.read(p.evidence_ref)==before[1]
    assert service.reader.detail(source.name,p.session.session_id).document['events']!=view['events']


@pytest.mark.parametrize('bad_target',['source','absent','private'])
def test_write_rejected_outside_workspace(tmp_path,persisted,bad_target):
    source,p,store,_=persisted;service=DesktopWorkspace(tmp_path)
    database={'source':source.name,'absent':'absent.sqlite3','private':'_backup/private.sqlite3'}[bad_target]
    with pytest.raises(HistoryError,match='workspace_required'):
        service.review(database,p.session.session_id,request_for(p),p.events[-1].evidence_ref)


def test_review_conflict_and_evidence_change_blocked(tmp_path,persisted):
    source,p,store,service,database=setup_workspace(tmp_path,persisted)
    request=request_for(p);service.review(database,p.session.session_id,request,p.events[-1].evidence_ref)
    with pytest.raises(HistoryError,match='review_conflict'):
        service.review(database,p.session.session_id,request_for(p),p.events[-1].evidence_ref)
    store.path(p.evidence_ref).write_bytes(b'tampered fixture')
    with pytest.raises(HistoryError,match='evidence_invalid'):
        service.review(database,p.session.session_id,request,p.events[-1].evidence_ref)


def corpus_fixture(tmp_path):
    processor,r,transcriber,run=fixture(tmp_path)
    path=tmp_path/CORPUS;path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(dict(clips=[dict(case_id='A03',human_verified=True,consent_ref='permission.json',
        actual_audio_path=r.audio_ref,audio_sha256=r.expected_sha256,origin_reported='human_recording')])),encoding='utf-8')
    return transcriber


def test_process_and_persistence_retry_do_not_repeat_asr(tmp_path,persisted):
    source,p,store,service,database=setup_workspace(tmp_path,persisted)
    transcriber=corpus_fixture(tmp_path);service.transcriber_factory=lambda:transcriber
    stages=[]
    with patch('medassistmultimodal.infrastructure.desktop_workspace.register_audio_sqlite',side_effect=sqlite3.OperationalError('fixture failure')):
        result=service.process(database,'PAT-001','A03',datetime.now(timezone.utc),stages.append)
    assert not result.persisted and stages==['validating','loading_model','processing','saving']
    retry=service.retry_persistence(database,result.run_id)
    assert retry.persisted
    assert service.retry_persistence(database,result.run_id)==retry
    transcriber.transcribe_with_details.assert_called_once()
    view=service.reader.detail(database,UUID(result.session_id)).document
    assert view['documents'][0]['evidence']['llm']['status']=='disabled'
    assert all(r['event']['review_status']=='pending_review' for r in view['events'])


def test_invalid_audio_hash_and_naive_time_before_asr(tmp_path,persisted):
    source,p,store,service,database=setup_workspace(tmp_path,persisted)
    transcriber=corpus_fixture(tmp_path);service.transcriber_factory=lambda:transcriber
    with pytest.raises(ValueError):service.process(database,'PAT-001','A03',datetime(2026,11,7))
    (tmp_path/'audio.mp3').write_bytes(b'changed fixture')
    with pytest.raises(HistoryError,match='audio_changed'):
        service.process(database,'PAT-001','A03',datetime.now(timezone.utc))
    transcriber.transcribe_with_details.assert_not_called()


def pump(root,app):
    deadline=time.monotonic()+4
    while app.worker.busy and time.monotonic()<deadline:
        root.update();time.sleep(.005)
    root.update();assert not app.worker.busy


@pytest.fixture(scope='module')
def tk_runtime():
    try:root=tk.Tk()
    except tk.TclError as exc:
        if 'display' in str(exc).lower():pytest.skip('Tk display unavailable: '+str(exc))
        raise
    root.withdraw()
    yield root
    # Finalize widget/variable cycles on Tk's owner thread before later worker tests.
    import gc
    gc.collect()
    root.destroy()
    gc.collect()


@pytest.fixture
def window(tmp_path,persisted,tk_runtime):
    from medassistmultimodal.desktop_workflow import WorkflowApp
    root=tk.Toplevel(tk_runtime);root.withdraw()
    app=WorkflowApp(root,reader=SQLiteHistoryReader(tmp_path),workspace=DesktopWorkspace(tmp_path),project_root=tmp_path)
    app.database.set(persisted[0].name);app.load_history();pump(root,app)
    yield root,app
    if app.worker.busy:app.worker.thread.join(3);app.worker.drain()
    try:root.after_cancel(app.poll_id);root.destroy()
    except tk.TclError:pass


def test_ui_async_selection_and_historical_review_blocked(window):
    root,app=window
    iid=app.sessions.get_children()[0];app.sessions.selection_set(iid);app.select_session();pump(root,app)
    assert app.state.detail and app.state.status=='ready'
    event=app.events.get_children()[0];app.events.selection_set(event);app.select_event()
    with patch('medassistmultimodal.desktop_workflow.messagebox.askyesno') as confirm:
        app.submit_review(ReviewStatus.REVIEWED)
    confirm.assert_not_called();assert 'cópia de trabalho' in app.status.get()


def test_ui_heartbeat_and_close_wait_for_worker(window):
    root,app=window;release=Event();heartbeat=[]
    app.dispatch(lambda progress:release.wait(2),lambda result:None,'test fixture')
    root.after(5,lambda:heartbeat.append(True))
    deadline=time.monotonic()+.1
    while time.monotonic()<deadline:root.update();time.sleep(.005)
    assert heartbeat and app.worker.busy
    with patch('medassistmultimodal.desktop_workflow.messagebox.askyesno',return_value=True):app.request_close()
    assert app.closing and app.worker.busy
    release.set();app.worker.thread.join(2)
    deadline=time.monotonic()+2
    while app.worker.busy and time.monotonic()<deadline:
        root.update();time.sleep(.005)
    assert not app.worker.busy


def test_ui_new_context_error_clears_detail(window):
    root,app=window
    iid=app.sessions.get_children()[0];app.sessions.selection_set(iid);app.select_session();pump(root,app)
    app.database.set('not-here.sqlite3');app.load_history();pump(root,app)
    assert app.state.status=='error' and app.state.detail is None and not app.sessions.get_children()


def test_ui_review_requires_fields_confirmation_and_reuses_request(window,tmp_path):
    root,app=window
    database=app.workspace.create_copy(app.current_database,'PAT-001')
    app.database.set(database);app.load_history();pump(root,app)
    iid=app.sessions.get_children()[0];app.sessions.selection_set(iid);app.select_session();pump(root,app)
    # Choose a pending item rather than approving all items.
    event=app.events.get_children()[-1];app.events.selection_set(event);app.select_event()
    with patch('medassistmultimodal.desktop_workflow.messagebox.askyesno') as confirm:
        app.submit_review(ReviewStatus.REVIEWED)
    confirm.assert_not_called()
    app.reviewer.set('test-only-reviewer');app.reason.set('Automated UI fixture, not clinical review')
    with patch('medassistmultimodal.desktop_workflow.messagebox.askyesno',return_value=False):
        app.submit_review(ReviewStatus.REVIEWED)
    assert app.pending_review is None
    with patch('medassistmultimodal.desktop_workflow.messagebox.askyesno',return_value=True):
        app.submit_review(ReviewStatus.REVIEWED)
        request=app.pending_review[2]
        app.submit_review(ReviewStatus.REVIEWED)  # Busy: must not create another request.
        assert app.pending_review[2] is request
        pump(root,app)
    app.retry_review();pump(root,app)
    detail=app.reader.detail(database,UUID(iid)).document
    assert len(detail['review_histories'][str(request.event_id)])==1
    assert app.pending_review[2] is request


def test_ui_changed_fields_block_writes_until_consulted(window):
    root,app=window
    database=app.workspace.create_copy(app.current_database,'PAT-001')
    app.database.set(database);app.load_history();pump(root,app)
    app.patient.set('PAT-999')
    with patch('medassistmultimodal.desktop_workflow.messagebox.askyesno') as confirm:
        app.process_audio();app.create_workspace()
    confirm.assert_not_called()
    assert 'Consultar' in app.status.get()


# Keep widget checks in the same Tcl runtime instead of recreating interpreters.
from tests.unit.test_desktop_vitals import vital_db, check_tk_vitals_selection_samples_and_review_block


def test_tk_vitals_selection_samples_and_review_block(tmp_path,vital_db,tk_runtime):
    check_tk_vitals_selection_samples_and_review_block(tmp_path,vital_db,tk_runtime)


from tests.unit.test_desktop_prescriptions import prescription_db, check_tk_prescription_consultation


def test_tk_prescription_consultation(tmp_path,prescription_db,tk_runtime):
    check_tk_prescription_consultation(tmp_path,prescription_db,tk_runtime)

from tests.unit.test_structured_workspace import structured, check_tk_structured_registration_and_review


def test_tk_structured_registration_and_review(tmp_path,structured,tk_runtime):
    check_tk_structured_registration_and_review(tmp_path,structured,tk_runtime)

from tests.unit.test_desktop_video import video_db, check_tk_video_history_review_export_and_clear


def test_tk_video_history_review_export_and_clear(tmp_path,video_db,tk_runtime):
    check_tk_video_history_review_export_and_clear(tmp_path,video_db,tk_runtime)


from tests.unit.test_desktop_video import check_tk_video_preview_keeps_table_scrollable


@pytest.mark.parametrize('size,scaling',[('900x600',1.333),('1100x750',1.333),('1400x900',2.0)])
def test_tk_video_preview_keeps_table_scrollable(tmp_path,video_db,tk_runtime,size,scaling):
    check_tk_video_preview_keeps_table_scrollable(tmp_path,video_db,tk_runtime,size,scaling)


from tests.unit.test_desktop_video import check_tk_frame_selection_latest_wins_and_stale_clear


def test_tk_frame_selection_latest_wins_and_stale_clear(tmp_path,video_db,tk_runtime):
    check_tk_frame_selection_latest_wins_and_stale_clear(tmp_path,video_db,tk_runtime)

from tests.unit.test_desktop_text import text_workspace, check_tk_optional_text_default_confirmation_and_render


def test_tk_optional_text_default_confirmation_and_render(tmp_path,text_workspace,tk_runtime):
    check_tk_optional_text_default_confirmation_and_render(tmp_path,text_workspace,tk_runtime)

from tests.unit.test_desktop_summary import summary_data, check_tk_summary_selection_generation_export_and_context


def test_tk_summary_selection_generation_export_and_context(tmp_path,summary_data,tk_runtime):
    check_tk_summary_selection_generation_export_and_context(tmp_path,summary_data,tk_runtime)


def test_tk_elbow_case_selection_and_render(tmp_path,video_db,tk_runtime):
    from tests.unit.test_elbow_rgb_ui import check_tk_elbow_case_selection_and_render
    check_tk_elbow_case_selection_and_render(tmp_path,video_db,tk_runtime)


def test_tk_prescription_expectation(tmp_path,structured,tk_runtime):
    from tests.unit.test_prescription_expectation import check_tk_prescription_expectation
    check_tk_prescription_expectation(tmp_path,structured,tk_runtime)


from tests.unit.test_acoustic_ui import acoustic_db


def test_tk_acoustic_registration(tmp_path,acoustic_db,tk_runtime):
    from tests.unit.test_acoustic_ui import check_tk_acoustic_registration
    check_tk_acoustic_registration(tmp_path,acoustic_db,tk_runtime)


def test_tk_simplified_navigation(tmp_path,summary_data,tk_runtime):
    from tests.unit.test_desktop_simplified import check_simplified_navigation
    check_simplified_navigation(tmp_path,summary_data,tk_runtime)


@pytest.mark.parametrize('size',['1280x820','900x600'])
def test_tk_video_simplified_layout(tmp_path,video_db,tk_runtime,size):
    from tests.unit.test_video_simplified_layout import check_video_simplified_layout
    check_video_simplified_layout(tmp_path,video_db,tk_runtime,size)


def test_tk_audio_simplified_layout(tmp_path,text_workspace,tk_runtime):
    from tests.unit.test_audio_simplified_layout import check_audio_simplified_layout
    check_audio_simplified_layout(tmp_path,text_workspace,tk_runtime)


def test_tk_anomaly_simplified_layout(tmp_path,structured,tk_runtime):
    from tests.unit.test_anomaly_simplified_layout import check_anomaly_simplified_layout
    check_anomaly_simplified_layout(tmp_path,structured,tk_runtime)


def test_tk_review_simplified_layout(tmp_path,summary_data,tk_runtime):
    from tests.unit.test_review_simplified_layout import check_review_simplified_layout
    check_review_simplified_layout(tmp_path,summary_data,tk_runtime)


def test_tk_custom_appearance_workflow(tmp_path,summary_data,tk_runtime):
    from tests.unit.test_desktop_custom import check_custom_appearance_workflow
    check_custom_appearance_workflow(tmp_path,summary_data,tk_runtime)
