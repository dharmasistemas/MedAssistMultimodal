"""Readable review and report presentation over existing audited operations."""
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from types import SimpleNamespace

from medassistmultimodal.desktop import label, local_time
from medassistmultimodal.domain.events import ReviewStatus


def event_kind(row):
    item = row['evidence_item']; reference = row['event']['evidence_ref']; modality = row['modality']
    if modality == 'audio':
        if item.get('classification') == 'candidate_for_human_review':
            return 'Candidato', 'Menção de '+item.get('term','termo')
        if 'term' in item:
            return 'Contexto', 'Menção de '+item['term']
    if modality == 'vitals' and 'rule_id' in item:
        from medassistmultimodal.desktop_multimodal import CHANNELS
        return 'Candidato', CHANNELS.get(item.get('channel'),'Ocorrência de vitais')
    if '/expectation_candidates/' in reference:
        return 'Candidato', 'Divergência do plano de prescrição'
    if modality == 'prescriptions' and item.get('kind') in ('modified','included','removed'):
        return 'Alteração', 'Mudança de item da prescrição'
    if '/deviation_candidates/' in reference:
        return 'Candidato', 'Flexão de cotovelo — experimental'
    if modality == 'acoustics' and '/candidates/' in reference:
        return 'Candidato', 'Pausas frequentes — experimental'
    if '/cycles/' in reference:
        return 'Técnico', 'Ciclo de movimento experimental'
    if 'quality' in item or '/quality_intervals/' in reference:
        return 'Qualidade', 'Limitação técnica dos dados'
    return 'Resumo', 'Resumo da execução'


def review_item_text(row, histories):
    category, title = event_kind(row)
    event = row['event']; item = row['evidence_item']
    lines = [title, f"Tipo: {category} · Estado: {label(event['review_status'])}", '']
    if category == 'Candidato':
        lines.append('Candidato experimental para revisão; não é diagnóstico ou urgência validada.')
    else:
        lines.append('Registro contextual/técnico; não deve ser contado automaticamente como alerta clínico.')
    if item.get('sentence'):
        lines.append('Trecho: '+item['sentence'])
    if 'values' in item and 'unit' in item:
        lines.append(f"Valores: {item['values']} {item['unit']} · limiar: {item.get('threshold','não informado')}")
    if 'first_timestamp' in item:
        lines.append(f"Período: {local_time(item['first_timestamp'])} até {local_time(item['last_timestamp'])}")
    if 'differences' in item:
        from medassistmultimodal.desktop_multimodal import PRESCRIPTION_FIELDS
        for difference in item['differences']:
            field = PRESCRIPTION_FIELDS.get(difference['field'], 'Presença do item' if difference['field']=='presence' else difference['field'])
            lines.append(f"• {difference['item_id']} · {field}: esperado {difference['expected']}; observado {difference['observed']}")
    if item.get('evidence_frame') is not None:
        lines.append(f"Frame de evidência: {item['evidence_frame']}")
    if 'long_pause_count' in item:
        lines.append(f"Pausas longas calculadas: {item['long_pause_count']}; não identificam condição médica.")
    lines += ['', 'HISTÓRICO DE REVISÃO']
    count = 0
    for audit in histories:
        for record in audit.get('events', []):
            if record.get('event_id') != event['event_id']:
                continue
            count += 1
            lines += [f"• {label(record['after_status'])} · {local_time(record['reviewed_at'])}",
                      f"  Revisor: {record['reviewer_ref']}", f"  Motivo: {record['reason']}"]
            if record.get('scope') == 'technical_simulation':
                lines.append('  Simulação técnica de teste; não é revisão clínica.')
    if not count:
        lines.append('Nenhuma revisão registrada para este item.')
    lines += ['', 'Revisado significa conferência declarada, não certificação clínica. A evidência completa permanece disponível abaixo.']
    return '\n'.join(lines)


def report_preview_text(snapshot):
    from medassistmultimodal.desktop_audio_layout import audio_result_text
    from medassistmultimodal.desktop_anomaly_layout import anomaly_result_text
    from medassistmultimodal.desktop_video_layout import video_result_text
    doc = snapshot.document
    lines = ['MedAssistMultimodal — prévia resumida',
             f"Resultados selecionados: {len(doc['session_ids'])} · gerado em {local_time(doc['generated_at'])}",
             'Fontes independentes. Sem correlação clínica, sincronização ou diagnóstico demonstrados.',
             'Os arquivos TXT/JSON preservam o conteúdo completo e a auditoria; esta prévia é resumida.',
             'Revisões: '+', '.join(f'{label(k)}: {v}' for k,v in sorted(doc['counts']['review_status'].items()))]
    for group, title in (('patient_sessions','PACIENTE FICTÍCIO — REGISTROS SIMULADOS'),
                         ('dataset_sessions','VÍDEO — DATASET INDEPENDENTE DO PACIENTE FICTÍCIO')):
        lines += ['', title]
        if not doc[group]:
            lines.append('Nenhum resultado selecionado nesta origem.')
        for data in doc[group]:
            detail = SimpleNamespace(document=data)
            lines += ['', 'Horário da sessão/cenário: '+local_time(data['session']['started_at'])]
            if data.get('documents') or data.get('acoustics'):
                lines.append(audio_result_text(detail))
            if data.get('vitals') or data.get('prescriptions'):
                lines.append(anomaly_result_text(detail))
            if data.get('videos'):
                lines.append(video_result_text(detail))
    return '\n'.join(lines)


class ReviewPanel:
    def __init__(self, app):
        self.app = app; self.catalog = {}; self.catalog_context = None; self.current_event = None
        for child in app.review_page.pack_slaves():
            child.pack_forget()
        shell = ttk.Frame(app.review_page, padding=10); shell.pack(fill='both',expand=True)
        shell.columnconfigure(0,weight=1,minsize=260); shell.columnconfigure(1,weight=2,minsize=320); shell.rowconfigure(0,weight=1)
        left = ttk.Frame(shell); left.grid(row=0,column=0,sticky='nsew',padx=(0,12))
        self.choice = tk.StringVar()
        ttk.Label(left,text='Resultado para revisar',font=('Segoe UI',11,'bold')).pack(anchor='w')
        ttk.Button(left,text='Carregar resultados desta base',command=app.load_report_catalog).pack(fill='x',pady=6)
        self.choices = ttk.Combobox(left,textvariable=self.choice,state='readonly',width=25)
        self.choices.pack(fill='x',pady=3); self.choices.bind('<<ComboboxSelected>>',self.select_result)
        self.identity = tk.StringVar(value='Selecione um resultado ou use Revisar resultado na aba de origem.')
        ttk.Label(left,textvariable=self.identity,wraplength=300).pack(anchor='w',pady=8)
        ttk.Label(left,text='Itens — nem todo registro é um alerta').pack(anchor='w',pady=4)
        table = app.events.master
        table.pack(in_=left,fill='both',expand=True)
        table.lift()
        app.events.configure(show='headings',displaycolumns=('kind','status'),height=8)
        app.events.heading('kind',text='Item / tipo'); app.events.heading('status',text='Estado')
        app.events.column('kind',width=220,minwidth=100,stretch=True); app.events.column('status',width=110,minwidth=90,stretch=False)
        app.events.pack_configure(fill='both',expand=True)
        horizontal = ttk.Scrollbar(table,orient='horizontal',command=app.events.xview)
        horizontal.pack(side='bottom',fill='x'); app.events.configure(xscrollcommand=horizontal.set)
        right = ttk.Frame(shell); right.grid(row=0,column=1,sticky='nsew')
        right.columnconfigure(0,weight=1); right.rowconfigure(1,weight=1,minsize=80)
        ttk.Label(right,text='Item e decisão humana',font=('Segoe UI',11,'bold')).grid(row=0,column=0,sticky='w',pady=(0,5))
        self.detail = ScrolledText(right,wrap='word',width=30,height=8,font=('Segoe UI',10),padx=8,pady=8)
        self.detail.grid(row=1,column=0,sticky='nsew')
        form = ttk.Frame(right); form.grid(row=2,column=0,sticky='ew',pady=6); form.columnconfigure(0,weight=1)
        ttk.Label(form,text='Identificação do revisor').grid(row=0,column=0,sticky='w')
        ttk.Entry(form,textvariable=app.reviewer).grid(row=1,column=0,sticky='ew',pady=(2,5))
        ttk.Label(form,text='Motivo da decisão (uma linha)').grid(row=2,column=0,sticky='w')
        ttk.Entry(form,textvariable=app.reason).grid(row=3,column=0,sticky='ew',pady=2)
        actions = ttk.Frame(right); actions.grid(row=3,column=0,sticky='ew')
        self.review_button = ttk.Button(actions,text='Registrar como revisado',command=lambda:app.submit_review(ReviewStatus.REVIEWED))
        self.review_button.pack(side='left',pady=4)
        self.dismiss_button = ttk.Button(actions,text='Descartar com motivo',command=lambda:app.submit_review(ReviewStatus.DISMISSED))
        self.dismiss_button.pack(side='left',padx=5,pady=4)
        ttk.Button(right,text='Evidência completa e retentativa ▸',command=self.toggle_review_technical).grid(row=4,column=0,sticky='w',pady=4)
        self.technical = ttk.Frame(right)
        app.event_detail.configure(width=30,height=5)
        app.event_detail.frame.pack(in_=self.technical,fill='both',expand=True)
        app.event_detail.frame.lift()
        ttk.Button(self.technical,text='Reenviar mesma revisão pendente',command=app.retry_review).pack(anchor='w',pady=3)
        self.technical_open = False
        self.clear()

        # Keep the original report text/snapshot/export machinery under a readable preview.
        for child in app.summary_page.pack_slaves():
            child.pack_forget()
        export = ttk.Frame(app.summary_page,padding=10); export.pack(fill='both',expand=True)
        self.export_surface = export
        export.columnconfigure(0,weight=1); export.rowconfigure(4,weight=1,minsize=80)
        controls = ttk.Frame(export); controls.grid(row=0,column=0,sticky='ew')
        ttk.Button(controls,text='Carregar resultados',command=app.load_report_catalog).pack(side='left')
        ttk.Button(controls,text='Gerar prévia',command=app.generate_report).pack(side='left',padx=6)
        ttk.Button(controls,text='Exportar TXT e JSON',command=app.export_report).pack(side='left')
        ttk.Label(export,text='Clique nas linhas para incluir/retirar até 20 resultados. Fontes independentes permanecem separadas.',wraplength=800).grid(row=1,column=0,sticky='w',pady=5)
        report_table = app.report_sessions.master
        report_table.pack_forget(); report_table.grid(in_=export,row=2,column=0,sticky='ew')
        report_table.lift()
        app.report_sessions.configure(height=5)
        app.report_sessions.heading('#0',text='Resultado'); app.report_sessions.column('#0',width=80,minwidth=65,stretch=False)
        app.report_sessions.bind('<Button-1>',self.toggle_report_row)
        self.selection_text = tk.StringVar(value='Nenhum resultado selecionado.')
        ttk.Label(export,textvariable=self.selection_text).grid(row=3,column=0,sticky='w',pady=4)
        self.preview = ScrolledText(export,wrap='word',width=30,height=8,font=('Segoe UI',10),padx=8,pady=8)
        self.preview.grid(row=4,column=0,sticky='nsew')
        app.set_text(self.preview,'Selecione os resultados e gere a prévia antes de exportar.')
        ttk.Button(export,text='Conteúdo integral para exportação ▸',command=self.toggle_report_technical).grid(row=5,column=0,sticky='w',pady=4)
        self.full_report = ttk.Frame(export)
        app.report_text.configure(width=30,height=5)
        app.report_text.frame.pack(in_=self.full_report,fill='both',expand=True)
        app.report_text.frame.lift()
        self.full_report_open = False

    def populate_catalog(self,rows):
        self.catalog = {f'{i+1} · {row["modalities"]} · {row["subject"]} · {local_time(row.get("registered_at") or row["started_at"])}':row
                        for i,row in enumerate(rows)}
        self.catalog_context = self.app.report_context
        self.choices.configure(values=tuple(self.catalog))
        for i,row in enumerate(rows):
            self.app.report_sessions.item(row['session_id'],text=str(i+1))
        if self.app.state.detail:
            self.show(self.app.state.detail)

    def clear_catalog(self):
        self.catalog = {}; self.catalog_context = None; self.choice.set(''); self.choices.configure(values=())
        self.selection_text.set('Nenhum resultado selecionado.')

    def select_result(self,_event=None):
        app = self.app; row = self.catalog.get(self.choice.get())
        if app.worker.busy or not row or self.catalog_context != (app.database.get(),app.patient.get()):
            return
        sid = row['session_id']
        if row['modalities'] == 'Vídeo':
            app.video_ids = [x['session_id'] for x in self.catalog.values() if x['modalities']=='Vídeo']
            app.video_choices.configure(values=app.video_ids); app.video_session.set(sid); app.select_video()
        else:
            if not app.sessions.exists(sid):
                # The report catalog may contain a session added since the last history query.
                app.sessions.insert('','end',iid=sid,text=sid,values=(local_time(row.get('registered_at') or row['started_at']),row['modalities']))
            app.sessions.selection_set(sid); app.select_session()
        if app.worker.busy and app.on_success:
            original = app.on_success
            def ready(detail):
                original(detail)
                if app.state.detail is detail:
                    app.tabs.select(app.review_tab); app.review_views.select(0)
            app.on_success = ready

    def show(self,detail):
        data = detail.document; session = data['session']; sid = session['session_id']
        self.choice.set(next((name for name,row in self.catalog.items() if row['session_id']==sid),'Resultado carregado da aba de origem'))
        self.identity.set(('Dataset independente do paciente fictício' if session['patient_id'] is None else 'Paciente fictício '+session['patient_id'])
                          +' · '+('Registro: '+local_time(data['registered_at']) if data.get('registered_at') else 'Sessão: '+local_time(session['started_at'])))
        for row in data['events']:
            category,title = event_kind(row)
            self.app.events.item(row['event']['event_id'],values=(label(row['event']['review_status']),category+' · '+title))

    def clear(self):
        self.current_event = None; self.choice.set('')
        self.app.reason.set('')
        self.identity.set('Selecione um resultado verificado para consultar os itens.')
        self.app.set_text(self.detail,'Selecione um item para conferir evidência, estado e histórico antes da decisão.')
        self.app.set_text(self.app.event_detail,'Selecione um item verificado para consultar a evidência completa.')
        self.review_button.configure(state='disabled'); self.dismiss_button.configure(state='disabled')

    def show_event(self):
        app = self.app; selected = app.events.selection()
        if not selected or app.state.detail is None:
            return
        data = app.state.detail.document
        row = next((r for r in data['events'] if r['event']['event_id']==selected[0]),None)
        if row is None:
            return
        if self.current_event != selected[0]:
            app.reason.set(''); self.current_event = selected[0]
        app.set_text(self.detail,review_item_text(row,data['review_histories'].get(selected[0],[])))
        writable = (row['event']['review_status']=='pending_review' and app.current_database
                    and app.database.get()==app.current_database and app.patient.get()==app.loaded_patient
                    and app.workspace.is_workspace(app.current_database))
        self.review_button.configure(state='normal' if writable else 'disabled')
        self.dismiss_button.configure(state='normal' if writable else 'disabled')

    def invalidate_report(self):
        self.app.set_text(self.preview,'Seleção, contexto ou revisão alterada. Gere uma nova prévia antes de exportar.')
        self.selection_text.set(f'{len(self.app.report_sessions.selection())} resultado(s) selecionado(s).')

    def toggle_report_row(self,event):
        if self.app.worker.busy:
            return 'break'
        row = self.app.report_sessions.identify_row(event.y)
        if row:
            tree = self.app.report_sessions
            tree.selection_remove(row) if row in tree.selection() else tree.selection_add(row)
            tree.focus(row)
            return 'break'

    def toggle_review_technical(self):
        self.technical_open = not self.technical_open
        self.technical.grid(row=5,column=0,sticky='ew') if self.technical_open else self.technical.grid_remove()

    def toggle_report_technical(self):
        self.full_report_open = not self.full_report_open
        self.full_report.grid(row=6,column=0,sticky='ew') if self.full_report_open else self.full_report.grid_remove()
