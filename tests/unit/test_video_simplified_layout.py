"""Video layout checks called from the shared Tk runtime."""
import tkinter as tk
from unittest.mock import patch
from uuid import uuid4


def check_video_simplified_layout(tmp_path, video_db, tk_runtime, size):
    from medassistmultimodal.desktop_simplified import SimplifiedApp
    from tests.unit.test_desktop_workflow import pump
    from tests.unit.test_elbow_deviation import prepare_v2

    service, database, old, _ = video_db
    ref = (service.writable_path(database).parent / f'layout_{uuid4()}.json').relative_to(tmp_path).as_posix()
    prepared = prepare_v2(old, ref, [140.] * 5)
    service._persist_video(database, prepared)
    evidence = (tmp_path / ref).read_bytes()
    root = tk.Toplevel(tk_runtime)
    app = SimplifiedApp(root, reader=service.reader, workspace=service, project_root=tmp_path)
    try:
        root.geometry(size); root.update()
        assert not app.video_manual_open and not app.video_technical_open
        app.toggle_video_manual(); root.update()
        assert app.video_manual.winfo_rooty() < app.video_process_button.winfo_rooty()
        fields = [c for c in app.video_manual.winfo_children() if c.winfo_class() == 'TEntry']
        assert fields[0].winfo_rooty() == fields[1].winfo_rooty()
        app.video_case.set('Manual (ciclos)'); app.choose_video_case()
        assert app.video_manual_open
        app.toggle_video_manual()
        app.database.set(database); app.load_history(); pump(root, app)
        app.load_video_history(); pump(root, app)
        app.video_session.set(str(prepared.session.session_id)); app.select_video(); pump(root, app)
        assert app.tabs.select() == str(app.video_tab)
        assert 'Sinal experimental' in app.video_result.get()
        assert 'sem validação clínica' in app.video_result.get()
        assert app.video_samples.get_children()
        assert not app.video_summary.winfo_ismapped()
        app.toggle_video_technical(); root.update()
        assert app.video_summary.winfo_ismapped()
        assert ref in app.video_summary.get('1.0', 'end')
        app.toggle_video_technical(); root.update()
        ppm = b'P6\n540 960\n255\n' + b'\x80\x80\x80' * (540*960)
        with patch.object(service, 'preview', return_value=ppm) as preview:
            app.video_samples.selection_set(app.video_samples.get_children()[0]); root.update(); pump(root, app)
        assert preview.call_count == 1
        root.update()
        assert app.preview_area.winfo_height() > app.preview_area.winfo_width()
        assert app.preview_image.height() > app.preview_image.width()
        assert app.video_samples.winfo_rootx() > app.preview_area.winfo_rootx() + app.preview_area.winfo_width()
        assert app.video_samples.winfo_height() >= 80
        assert app.video_samples.winfo_rooty() + app.video_samples.winfo_height() <= app.video_tab.winfo_rooty() + app.video_tab.winfo_height()
        app.video_samples.yview_moveto(1); root.update()
        assert app.video_samples.yview()[1] == 1.0
        app.database.set('missing.sqlite3'); app.load_history(); pump(root, app)
        assert not app.video_active and app.preview_image is None
        assert not app.video_samples.get_children()
        assert 'Sem resultado verificado' in app.video_result.get()
        assert (tmp_path / ref).read_bytes() == evidence
    finally:
        if app.worker.busy:
            app.worker.thread.join(3); app.worker.drain()
        root.after_cancel(app.poll_id); root.destroy()
