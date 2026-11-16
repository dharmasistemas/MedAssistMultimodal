"""Checks invoked from the shared Tk runtime in test_desktop_workflow."""
import tkinter as tk


def check_simplified_navigation(tmp_path, summary_data, tk_runtime):
    from medassistmultimodal.desktop_simplified import SimplifiedApp
    from medassistmultimodal.infrastructure.desktop_text import TextWorkspace
    from tests.unit.test_desktop_workflow import pump

    _, database, ids, _, _, _ = summary_data
    root = tk.Toplevel(tk_runtime)
    workspace = TextWorkspace(tmp_path)
    app = SimplifiedApp(root, reader=workspace.reader, workspace=workspace, project_root=tmp_path)
    try:
        root.update()
        assert [app.tabs.tab(t, 'text') for t in app.tabs.tabs()] == [
            'Vídeo', 'Áudio e texto', 'Anomalias', 'Revisão e relatório']
        assert app.tabs.select() == str(app.video_tab)
        assert not app.database_bar.winfo_ismapped()
        assert str(app.history_pane) not in app.tabs.master.panes()
        for _ in range(2):
            app.toggle_workspace(); root.update()
            assert app.database_bar.winfo_ismapped()
            app.toggle_workspace(); root.update()
            assert not app.database_bar.winfo_ismapped()
            app.toggle_history(); root.update()
            assert str(app.history_pane) in app.tabs.master.panes()
            app.toggle_history(); root.update()
            assert str(app.history_pane) not in app.tabs.master.panes()
        assert not app.audio_actions.winfo_manager()
        assert app.audio_panel.frame.master is app.audio_tab
        assert not app.structured_actions.winfo_manager()
        assert app.anomaly_panel.frame.master is app.anomaly_tab
        assert not app.use_cloud_text.get()
        app.database.set(database); app.load_history(); pump(root, app)
        assert app.sessions.get_children()
        # New positions must not route vitals/prescriptions into the video/audio tab.
        for sid in app.sessions.get_children():
            app.sessions.selection_set(sid); app.select_session(); pump(root, app)
            if app.state.detail.document.get('vitals') or app.state.detail.document.get('prescriptions'):
                assert app.tabs.select() == str(app.anomaly_tab)
        app.tabs.select(app.review_tab)
        app.review_views.select(1)
        app.load_report_catalog(); pump(root, app)
        app.report_sessions.selection_set(ids); root.update()
        app.generate_report(); pump(root, app)
        assert app.report_snapshot is not None
        app.export_report(); pump(root, app)
        assert 'Exportação concluída' in app.status.get()
        app._set_busy(True)
        assert str(app.cloud_check.cget('state')) == 'disabled'
        app._set_busy(False)
        assert not app.use_cloud_text.get()
        app.patient.set('PAT-002')
        assert app.report_snapshot is None
    finally:
        if app.worker.busy:
            app.worker.thread.join(3); app.worker.drain()
        root.after_cancel(app.poll_id)
        root.destroy()
