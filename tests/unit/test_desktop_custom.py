"""CustomTkinter checks run inside the existing shared Tk runtime."""
import tkinter as tk
from unittest.mock import Mock,patch


def check_custom_appearance_workflow(tmp_path,summary_data,tk_runtime):
    import customtkinter as ctk
    from medassistmultimodal.desktop_custom import CustomApp,configure_appearance
    from medassistmultimodal.infrastructure.desktop_text import TextWorkspace
    from tests.unit.test_desktop_workflow import pump
    _,db,ids,_,source,_=summary_data;before=source.read_bytes()
    root=tk.Toplevel(tk_runtime)
    configure_appearance()
    provider=Mock(side_effect=AssertionError('Styling must not invoke models'))
    w=TextWorkspace(tmp_path,text_provider_factory=provider,transcriber_factory=provider)
    app=CustomApp(root,reader=w.reader,workspace=w,project_root=tmp_path)
    try:
        root.update()
        assert app.custom_buttons and isinstance(app.video_process_button,ctk.CTkButton)
        assert root.state()=='zoomed'
        assert all(b.cget('border_width')==1 and b.cget('border_color')=='#ffffff' for b in app.custom_buttons)
        from medassistmultimodal.desktop_custom import COLORS,TAB_PADDING,FONTS,VIDEO_INPUT_WIDTH,VIDEO_COLUMN_WIDTHS
        from tkinter import ttk
        style=ttk.Style(root)
        assert tuple(map(int,root.tk.splitlist(style.lookup('MAM.TNotebook.Tab','padding',('selected',)))))==TAB_PADDING
        assert style.lookup('MAM.TNotebook.Tab','padding',('selected',))==style.lookup('MAM.TNotebook.Tab','padding',('!selected',))
        assert style.lookup('MAM.TNotebook.Tab','background',('selected',))==COLORS['active']
        assert style.lookup('MAM.Treeview.Heading','background')==COLORS['active']
        assert int(app.video_inputs.master.cget('width'))==VIDEO_INPUT_WIDTH
        assert int(app.video_samples.column('quality','width'))==VIDEO_COLUMN_WIDTHS['quality']
        assert app.video_process_button.cget('font')==FONTS['button']
        assert isinstance(app.review_panel.review_button,ctk.CTkButton)
        assert app.video_samples.cget('style')=='MAM.Treeview'
        assert app.audio_panel.result.cget('background')=='#141820'
        # Replay pack during a DPI transition: no hidden legacy sibling remains.
        order = root.pack_slaves()
        for button in app.custom_buttons:
            if button.winfo_manager() == 'pack':
                saved = button._last_geometry_manager_call['kwargs']
                assert 'before' not in saved and 'after' not in saved
                button._set_scaling(1.5,1.5)
                button._set_scaling(1.0,1.0)
        root.update()
        assert root.pack_slaves() == order
        assert not app.use_cloud_text.get()
        area=next(b for b in app.custom_buttons if b.cget('text')=='Área de trabalho ▸')
        area.invoke();root.update();assert app.database_bar.winfo_ismapped()
        assert area.cget('fg_color')==COLORS['active']
        order=root.pack_slaves();assert order.index(app.tools)<order.index(app.database_bar)
        app.history_button.invoke();root.update()
        assert app.history_open and not app.workspace_open
        assert app.history_button.cget('fg_color')==COLORS['active']
        assert area.cget('fg_color')==COLORS['panel']
        app.history_button.invoke();root.update();assert not app.history_open
        app.tabs.select(app.audio_tab);root.update()
        assert {tip.text for tip in app.player_tooltips}=={'Ouvir','Pausar','Parar'}
        assert {tip.widget.cget('text') for tip in app.player_tooltips}=={'▶','⏸','■'}
        tip=app.player_tooltips[0]
        tip.schedule();assert tip.after_id is not None
        tip.hide();assert tip.after_id is None
        tip.show();root.update();assert tip.window is not None
        assert tip.window.winfo_children()[0].cget('text')=='Ouvir'
        tip.hide();assert tip.window is None
        app.video_manual_toggle.invoke();root.update();assert app.video_manual_open
        app.video_manual_toggle.invoke();root.update();assert not app.video_manual_open
        app.database.set(db);app.load_history()
        assert app.video_process_button.cget('state')=='disabled'
        with patch.object(w,'process_video') as process:app.video_process_button.invoke()
        process.assert_not_called()
        pump(root,app);assert app.video_process_button.cget('state')=='normal'
        app.load_report_catalog();pump(root,app)
        app.tabs.select(app.review_tab);app.review_views.select(1)
        app.report_sessions.selection_set(ids);root.update()
        next(b for b in app.custom_buttons if b.cget('text')=='Gerar prévia').invoke();pump(root,app)
        assert app.report_snapshot
        next(b for b in app.custom_buttons if b.cget('text')=='Exportar TXT e JSON').invoke();pump(root,app)
        assert 'Exportação concluída' in app.status.get()
        name=next(name for name,r in app.review_panel.catalog.items() if r['session_id']==ids[1])
        app.review_panel.choice.set(name);app.review_panel.select_result();pump(root,app)
        event=next(r['event']['event_id'] for r in app.state.detail.document['events'] if 'rule_id' in r['evidence_item'])
        app.events.selection_set(event);app.select_event();root.update()
        assert app.review_panel.review_button.cget('state')=='normal'
        app.reviewer.set('custom-fixture');app.reason.set('UI fixture only; no clinical validation')
        with patch('medassistmultimodal.desktop_workflow.messagebox.askyesno',return_value=False):
            app.review_panel.review_button.invoke()
        assert app.pending_review is None
        with patch('medassistmultimodal.desktop_workflow.messagebox.askyesno',return_value=True):
            app.review_panel.review_button.invoke()
        pump(root,app)
        assert app.review_panel.review_button.cget('state')=='disabled'
        with patch('medassistmultimodal.desktop_workflow.messagebox.askyesno') as confirm:
            app.review_panel.review_button.invoke()
        confirm.assert_not_called()
        assert 'custom-fixture' in app.review_panel.detail.get('1.0','end')
        provider.assert_not_called();assert source.read_bytes()==before
        root.geometry('900x600');root.update()
        assert app.review_panel.detail.winfo_height()>=60
    finally:
        if app.worker.busy:app.worker.thread.join(3);app.worker.drain()
        for tip in app.player_tooltips:tip.hide()
        app.audio_panel.stop();root.after_cancel(app.poll_id);root.destroy()
