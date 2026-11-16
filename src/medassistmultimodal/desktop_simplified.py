"""Presentation shell; processing, evidence and review stay in existing use cases."""
from tkinter import ttk

from medassistmultimodal.desktop_summary import SummaryApp


class SimplifiedApp(SummaryApp):
    """First approved increment: navigation and local actions, no provider changes."""

    simplified_video = True

    def __init__(self, root, *, audio_player=None, **kwargs):
        super().__init__(root, **kwargs)
        root.geometry('1280x820')
        # Stable widget identities, rather than positions, are used by callbacks.
        self.tabs.insert(0, self.video_tab)
        self.tabs.tab(self.audio_tab, text='Áudio e texto')
        self.tabs.tab(self.review_tab, text='Revisão e relatório')

        summary = root.nametowidget(self.tabs.tabs()[-1])
        self.summary_page = summary
        review_children = list(self.review_tab.pack_slaves())
        self.review_views = ttk.Notebook(self.review_tab)
        review_page = ttk.Frame(self.review_views)
        export_page = ttk.Frame(self.review_views)
        self.review_page, self.export_page = review_page, export_page
        self.review_views.add(review_page, text='Revisão humana')
        self.review_views.add(export_page, text='Relatório e exportação')
        for child in review_children:
            options = child.pack_info()
            options.pop('in', None)
            child.pack_forget()
            child.pack(in_=review_page, **options)
        self.review_views.pack(fill='both', expand=True)
        self.tabs.forget(summary)
        summary.pack(in_=export_page, fill='both', expand=True)

        self.tools = ttk.Frame(root)
        self.tools.pack(fill='x', padx=12, pady=4, before=self.tabs.master)
        ttk.Button(self.tools, text='Área de trabalho ▸', command=self.toggle_workspace).pack(side='left')
        ttk.Button(self.tools, text='Histórico de sessões ▸', command=self.toggle_history).pack(side='left', padx=8)
        ttk.Label(self.tools, text='Fontes independentes · dados simulados ou de dataset · sem diagnóstico').pack(side='left')
        self.workspace_open = False
        self.history_open = False
        self.database_bar.pack_forget()
        self.tabs.master.forget(self.history_pane)

        # Tk allows geometry management inside a descendant of the widget parent.
        # Keep existing variables/commands and the worker's recursive busy guard.
        self.audio_actions.pack_forget()
        self.audio_actions.pack(in_=self.audio_tab, fill='x', padx=8, pady=6,
                                before=self.audio_tab.pack_slaves()[0])
        self.structured_actions.pack_forget()
        self.structured_actions.pack(in_=self.anomaly_tab, fill='x', padx=8, pady=6,
                                     before=self.anomaly_tab.pack_slaves()[0])
        self._wrap_actions(self.audio_actions)
        self._wrap_actions(self.structured_actions)
        for child in root.winfo_children():
            if not isinstance(child, ttk.Label):
                continue
            if str(child.cget('text')).startswith('POC acadêmica'):
                child.configure(text='POC acadêmica — apoio à revisão profissional | Sem diagnóstico')
            variable = str(child.cget('textvariable'))
            if variable == str(self.context):
                child.pack_forget()
                child.pack(in_=self.audio_tab, fill='x', padx=8, before=self.audio.frame)
            elif variable == str(self.last_structured):
                child.pack_forget()
                child.pack(in_=self.anomaly_tab, fill='x', padx=8, before=self.anomaly_tabs)
        self.tabs.select(self.video_tab)
        from medassistmultimodal.desktop_audio_layout import AudioPanel
        self.audio_panel = AudioPanel(self, player=audio_player)
        from medassistmultimodal.desktop_anomaly_layout import AnomalyPanel
        self.anomaly_panel = AnomalyPanel(self)
        from medassistmultimodal.desktop_review_layout import ReviewPanel
        self.review_panel = ReviewPanel(self)
        self.database.trace_add('write', self._audio_context_changed)
        self.patient.trace_add('write', self._audio_context_changed)

    def _audio_context_changed(self, *args):
        self.audio_panel.stop()
        self.audio_panel.clear_history()
        self.set_text(self.audio_panel.result, 'Contexto alterado. Consulte a base e selecione um resultado verificado.')
        self.anomaly_panel.clear_history()
        self.anomaly_panel.clear()
        self.anomaly_panel.update_origin()
        self.state.begin()
        self.state.status = 'idle'
        self.events.delete(*self.events.get_children())
        self.review_panel.clear_catalog()
        self.review_panel.clear()

    def clear_details(self):
        super().clear_details()
        if hasattr(self, 'audio_panel'):
            self.audio_panel.stop()
            self.audio_panel.history_value.set('')
            self.set_text(self.audio_panel.result, 'Selecione um resultado de áudio verificado. A entrada à esquerda define a próxima execução.')
        if hasattr(self, 'anomaly_panel'):
            self.anomaly_panel.clear()
        if hasattr(self, 'review_panel'):
            self.review_panel.clear()

    def load_history(self):
        if self.worker.busy or self.closing:
            return
        if hasattr(self, 'audio_panel'):
            self.audio_panel.clear_history()
        if hasattr(self, 'anomaly_panel'):
            self.anomaly_panel.clear_history()
        super().load_history()
        if hasattr(self, 'audio_panel') and self.worker.busy and self.on_success:
            original = self.on_success
            def ready(rows):
                original(rows)
                if self.state.rows is rows:
                    self.audio_panel.populate_history(rows)
                    self.anomaly_panel.populate_history(rows)
            self.on_success = ready

    def select_session(self, _event=None):
        if self.worker.busy or self.closing:
            return
        super().select_session(_event)
        if self.worker.busy and self.on_success:
            original = self.on_success
            def ready(detail):
                original(detail)
                if self.state.detail is detail:
                    from medassistmultimodal.desktop_audio_layout import audio_result_text
                    self.set_text(self.audio_panel.result, audio_result_text(detail))
                    sid = detail.document['session']['session_id']
                    self.audio_panel.history_value.set(next((name for name,value in self.audio_panel.history_ids.items() if value == sid),'') )
                    self.anomaly_panel.show(detail)
                    self.review_panel.show(detail)
            self.on_success = ready

    def select_video(self, _event=None):
        if self.worker.busy or self.closing:
            return
        super().select_video(_event)
        if self.worker.busy and self.on_success:
            original = self.on_success
            def ready(detail):
                original(detail)
                if self.state.detail is detail:
                    self.review_panel.show(detail)
            self.on_success = ready

    def select_event(self, _event=None):
        if self.worker.busy or self.closing:
            return
        super().select_event(_event)
        if hasattr(self, 'review_panel'):
            self.review_panel.show_event()

    def invalidate_report(self, *args):
        super().invalidate_report(*args)
        if hasattr(self, 'review_panel'):
            self.review_panel.invalidate_report()

    def clear_report_catalog(self, *args):
        super().clear_report_catalog(*args)
        if hasattr(self, 'review_panel'):
            self.review_panel.clear_catalog()

    def load_report_catalog(self):
        if self.worker.busy or self.closing:
            return
        context = self.current_database, self.loaded_patient
        super().load_report_catalog()
        if self.worker.busy and self.on_success:
            original = self.on_success
            def ready(rows):
                original(rows)
                if context == self.report_context == (self.database.get(),self.patient.get()):
                    self.review_panel.populate_catalog(rows)
            self.on_success = ready

    def generate_report(self):
        if self.worker.busy or self.closing:
            return
        super().generate_report()
        if self.worker.busy and self.on_success:
            original = self.on_success
            def ready(snapshot):
                original(snapshot)
                if self.report_snapshot is snapshot:
                    from medassistmultimodal.desktop_review_layout import report_preview_text
                    self.set_text(self.review_panel.preview,report_preview_text(snapshot))
            self.on_success = ready

    def retry_review(self):
        if self.worker.busy or self.closing:
            return
        stay_here = self.tabs.select() == str(self.review_tab)
        event_id = str(self.pending_review[2].event_id) if self.pending_review else None
        super().retry_review()
        if self.worker.busy:
            self.invalidate_report()
            if stay_here and self.on_success:
                original = self.on_success
                def saved(audit):
                    original(audit)
                    if self.worker.busy and self.on_success:
                        reload_detail = self.on_success
                        def ready(detail):
                            reload_detail(detail)
                            if self.state.detail is detail:
                                self.tabs.select(self.review_tab); self.review_views.select(0)
                                if event_id and self.events.exists(event_id):
                                    self.events.selection_set(event_id); self.select_event()
                        self.on_success = ready
                self.on_success = saved

    def process_audio(self):
        self.audio_panel.stop()
        if self.audio_panel.pilot.get():
            if self.worker.busy or self.closing:
                return
            previous = self.structured_modality.get(), self.structured_case.get()
            try:
                self.structured_modality.set('Pausas de áudio')
                self.structured_case.set(self.case.get())
                return self.register_structured_scenario()
            finally:
                self.structured_modality.set(previous[0]); self.structured_case.set(previous[1])
        return super().process_audio()

    def _set_busy(self, busy):
        if busy and hasattr(self, 'audio_panel'):
            self.audio_panel.stop()
        super()._set_busy(busy)
        if hasattr(self, 'audio_panel') and self.audio_panel.pilot.get():
            self.cloud_check.configure(state='disabled')

    def poll(self):
        super().poll()
        if hasattr(self, 'audio_panel') and not self.closing:
            self.audio_panel.poll()

    def request_close(self):
        if hasattr(self, 'audio_panel'):
            self.audio_panel.stop()
        super().request_close()

    def open_review(self):
        self.tabs.select(self.review_tab)
        self.review_views.select(0)

    @staticmethod
    def _wrap_actions(frame):
        """Two rows avoid the original full-window action strip overflowing a tab."""
        children = list(frame.pack_slaves())
        for child in children:
            child.pack_forget()
        for index, child in enumerate(children):
            child.grid(row=index // 4, column=index % 4, sticky='w', padx=4, pady=3)

    def toggle_workspace(self):
        self.workspace_open = not self.workspace_open
        if self.workspace_open:
            self.database_bar.pack(fill='x', padx=12, pady=6, before=self.tools)
        else:
            self.database_bar.pack_forget()

    def toggle_history(self):
        self.history_open = not self.history_open
        panes = self.tabs.master
        if self.history_open:
            panes.insert(0, self.history_pane, weight=1)
        else:
            panes.forget(self.history_pane)
