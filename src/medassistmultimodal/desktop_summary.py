"""Selected-session factual summary and JSON/TXT export; no provider calls."""
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from medassistmultimodal.desktop_text import TextAudioApp,ERRORS
from medassistmultimodal.desktop import local_time
from medassistmultimodal.infrastructure.desktop_summary import SummaryService

ERRORS.update(report_selection_invalid='Selecione de 1 a 20 sessões válidas desta base, sem duplicação.',
    report_stale='Resultados ou revisões mudaram. Gere a síntese novamente antes de exportar.',
    report_export_conflict='A pasta do relatório contém arquivos divergentes ou incompletos; nada foi sobrescrito.')


class SummaryApp(TextAudioApp):
    def __init__(self,root,**kwargs):
        self.report_snapshot=None;self.report_context=None
        super().__init__(root,**kwargs)
        self.summary_service=SummaryService(self.project_root,self.reader)
        frame=ttk.Frame(self.tabs);self.tabs.add(frame,text='Síntese e exportação')
        ttk.Label(frame,text='Escolha as sessões. Dataset de vídeo fica em seção independente; sem correlação clínica automática.',wraplength=650).pack(anchor='w',padx=8,pady=5)
        controls=ttk.Frame(frame);controls.pack(fill='x',padx=8)
        ttk.Button(controls,text='Carregar sessões',command=self.load_report_catalog).pack(side='left')
        ttk.Button(controls,text='Gerar síntese selecionada',command=self.generate_report).pack(side='left',padx=5)
        ttk.Button(controls,text='Exportar JSON e TXT',command=self.export_report).pack(side='left')
        ttk.Label(frame,text='Use Ctrl/clique ou Shift para selecionar várias linhas. Nenhuma análise ou chamada LLM será executada.').pack(anchor='w',padx=8,pady=4)
        table=ttk.Frame(frame);table.pack(fill='x',padx=8)
        self.report_sessions=ttk.Treeview(table,columns=('subject','modality','time'),show='tree headings',selectmode='extended',height=6)
        for c,t in [('#0','Sessão'),('subject','Identidade'),('modality','Modalidades'),('time','Horário registrado')]:
            self.report_sessions.heading(c,text=t);self.report_sessions.column(c,width=150)
        scroll=ttk.Scrollbar(table,orient='vertical',command=self.report_sessions.yview)
        self.report_sessions.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');self.report_sessions.pack(fill='x',expand=True)
        self.report_sessions.bind('<<TreeviewSelect>>',self.invalidate_report)
        self.report_text=ScrolledText(frame,wrap='word',font=('Segoe UI',10));self.report_text.pack(fill='both',expand=True,padx=8,pady=6)
        self.set_text(self.report_text,'Carregue as sessões desta base e escolha quais resultados deseja consultar.')
        self.database.trace_add('write',self.clear_report_catalog);self.patient.trace_add('write',self.clear_report_catalog)

    def invalidate_report(self,*args):
        self.report_snapshot=None
        if hasattr(self,'report_text'):self.set_text(self.report_text,'Seleção ou contexto alterado. Gere a síntese para consultar/exportar o estado atual.')

    def clear_report_catalog(self,*args):
        self.invalidate_report();self.report_context=None
        if hasattr(self,'report_sessions'):self.report_sessions.delete(*self.report_sessions.get_children())

    def load_history(self):
        if not self.worker.busy:self.clear_report_catalog()
        super().load_history()

    def _report_context_valid(self):
        if not self.current_database or self.database.get()!=self.current_database or self.patient.get()!=self.loaded_patient:
            self.clear_report_catalog();self.status.set('Consulte primeiro a base/paciente selecionados.');return False
        return True

    def load_report_catalog(self):
        if self.worker.busy or not self._report_context_valid():return
        self.clear_report_catalog();context=(self.current_database,self.loaded_patient)
        def ready(rows):
            if context!=(self.database.get(),self.patient.get()):return
            self.report_context=context
            for row in rows:self.report_sessions.insert('','end',iid=row['session_id'],text=row['session_id'],
                values=(row['subject'],row['modalities'],local_time(row.get('registered_at') or row['started_at'])))
            self.status.set(f'{len(rows)} sessões disponíveis. Selecione quais incluir na síntese.')
        self.dispatch(lambda progress:self.summary_service.catalog(*context),ready,'Carregando sessões para síntese…')

    def generate_report(self):
        if self.worker.busy or not self._report_context_valid():return
        context=(self.current_database,self.loaded_patient);selected=tuple(sorted(self.report_sessions.selection()))
        self.invalidate_report()
        if context!=self.report_context or not selected:
            self.status.set(ERRORS['report_selection_invalid']);return
        def ready(snapshot):
            if context!=(self.database.get(),self.patient.get()) or selected!=tuple(sorted(self.report_sessions.selection())):return
            self.report_snapshot=snapshot;self.set_text(self.report_text,snapshot.document['text'])
            self.status.set('Síntese factual verificada. Nenhum provider executado; revisão profissional continua necessária.')
        self.dispatch(lambda progress:self.summary_service.build(*context,selected),ready,'Conferindo evidências e gerando síntese factual…',lambda code:self.invalidate_report())

    def export_report(self):
        if self.worker.busy or not self._report_context_valid():return
        if self.report_snapshot is None:
            self.status.set('Gere a síntese selecionada antes de exportar.');return
        snapshot=self.report_snapshot
        self.dispatch(lambda progress:self.summary_service.export(snapshot),
            lambda directory:self.status.set('Exportação concluída: '+directory+' (summary.txt, summary.json e manifest.json)'),
            'Reconferindo revisões/evidências antes de exportar…',lambda code:self.invalidate_report())
