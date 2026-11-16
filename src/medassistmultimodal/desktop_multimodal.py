"""Desktop extension: verified audio, vital and prescription consultation."""
from medassistmultimodal.desktop_workflow import WorkflowApp, ERRORS  # Native environment first.
from medassistmultimodal.desktop import audio_text, label, local_time
from medassistmultimodal.infrastructure.desktop_vitals import MultimodalHistoryReader
from medassistmultimodal.infrastructure.desktop_workspace import DesktopWorkspace
from medassistmultimodal.infrastructure.structured_workspace import StructuredWorkspace
from medassistmultimodal.application.prescription_expectation_text import expectation_lines
from medassistmultimodal.application.register_acoustics import acoustic_lines
import argparse
from pathlib import Path
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText
from uuid import UUID

CHANNELS={'heart_rate':'Frequência cardíaca','spo2':'SpO₂','systolic':'Pressão sistólica','diastolic':'Pressão diastólica'}
QUALITY={'valid':'Válida','missing':'Ausente','invalid':'Inválida para a regra'}
TERMINATIONS={'end_of_series':'Fim da série','quality_gap':'Interrupção por qualidade',
              'return_to_range':'Retorno à faixa do perfil','direction_change':'Mudança de direção'}
CHANGES={'included':'Incluído','removed':'Removido','modified':'Modificado'}
PRESCRIPTION_FIELDS={'product_code':'Produto fictício','dose_value':'Dose registrada','dose_unit':'Unidade',
    'frequency_per_day':'Frequência por dia','route':'Via','duration_days':'Duração em dias','instructions':'Instruções'}
ERRORS.update(scenario_changed='O cenário difere do hash autorizado; nenhum novo registro foi criado.',
    scenario_unavailable='Cenário ou catálogo indisponível.',
    structured_input_rejected='Entrada rejeitada; nenhuma comparação válida foi registrada.',
    structured_persistence_failed='Gravação não confirmada. Reutilize a operação pendente; não gere nova execução.',
    registration_conflict='Conflito de execução ou estado de revisão. Não houve sobrescrita ou reabertura.',
    evidence_conflict='Arquivo de evidência divergente, preservado sem sobrescrever.',
    no_pending_registration='Não há registro preparado para essa retentativa nesta sessão do aplicativo.')
ERRORS.update(acoustic_input_invalid='Áudio ausente, alterado ou fora do perfil acústico; não equivale a ausência de sinal.',
    acoustic_decoder_unavailable='Decodificação local indisponível. Nenhum ASR ou modelo foi executado.')


def prescription_text(detail):
    records=detail.document.get('prescriptions',[])
    if not records:return 'Esta sessão não contém registros de comparação de prescrições.'
    blocks=[]
    for record in records:
        doc=record['evidence'];r=doc['result']
        lines=expectation_lines(doc)+['Integridade da evidência: verificada | Dados sintéticos | Comparação determinística real',
            f"Paciente fictício: {r['patient_id']} | Conjunto: {r['prescription_set_id']}",
            f"Execução: {doc['run_id']} | Processador: {r['processor']}",
            f"Antes: versão {r['before']['version']} | Emissão local: {local_time(r['before']['issued_at'])}",
            f"Depois: versão {r['after']['version']} | Emissão local: {local_time(r['after']['issued_at'])}",
            f"Itens antes: {len(r['before']['items'])} | Itens depois: {len(r['after']['items'])}",
            'Horários nominais fictícios; horário de processamento não registrado nesta evidência.',
            '', 'Comparação válida sem alterações.' if r['status']=='unchanged' else 'Comparação válida com alterações.',
            f"Incluídos: {r['included_count']} | Removidos: {r['removed_count']} | Modificados: {r['modified_count']}",
            '', 'ALTERAÇÕES POR ITEM']
        for change in r['changes']:
            lines.append(f"• {change['item_id']}: {CHANGES[change['kind']]}")
            for side,title in [('before','Antes'),('after','Depois')]:
                item=change[side]
                if item is None:lines.append(f'  {title}: item ausente nesta versão.')
                else:lines.append(f"  {title}: {item['product_code']} | {item['dose_value']} {item['dose_unit']} | {item['frequency_per_day']}/dia | {item['route']} | {item['duration_days']} dias | {item['instructions']}")
            for field in change['field_changes']:
                lines.append(f"  {PRESCRIPTION_FIELDS[field['field']]}: {field['before']} → {field['after']}")
            if change['unit_change_note']:
                lines.append('  Mudança de representação da unidade; sem inferir equivalência clínica ou aumento de dose.')
        if not r['changes']:lines.append('Nenhuma alteração entre as versões válidas comparadas.')
        lines+=['','As versões completas estão na aba Versões antes/depois.',
            'Doses preservadas como texto decimal exato. Nenhuma recomendação de tratamento.',
            f"Evidência: {record['reference']}",f"SHA-256: {record['sha256']}",
            f"Hash dos bytes da entrada original (declarado): {r['input_pair_sha256']}",
            'Snapshots canônicos conferidos; a entrada bruta original não é necessária para este detalhe.',
            'Consulte o estado atual e o histórico em Alertas e revisão. Gravações exigem cópia de trabalho.']
        blocks.append('\n'.join(lines))
    return '\n\n'.join(blocks)


def vital_text(detail):
    data=detail.document
    if not data['vitals']:return 'Esta sessão não contém registros de sinais vitais.'
    blocks=[]
    for record in data['vitals']:
        doc=record['evidence'];result=doc['result'];raw=record['raw_series']
        lines=['Integridade da evidência: verificada | Dados sintéticos | Processamento determinístico real',
            f"Cenário: {doc['scenario_id']} | Série: {result['series_id']}",
            f"Paciente fictício: {doc['subject']['patient_id']} | Execução: {doc['run_id']}",
            f"Sessão nominal (local): {local_time(data['session']['started_at'])}",
            'Horário de processamento: não registrado nesta evidência.',
            f"Processador: {result['processor']} | Perfil: {result['profile_version']}",
            f"Persistência do perfil: {result['persistence']} amostras consecutivas",
            '', 'COBERTURA POR CANAL (não é confiança clínica)']
        for coverage in result['coverage']:
            lines.append(f"• {CHANNELS[coverage['channel']]}: {coverage['valid_samples']}/{coverage['total_samples']} válidas ({coverage['fraction']:.2%})")
            if coverage['fraction']==0:lines.append('  Sem amostras válidas neste canal; ausência de ocorrência não indica normalidade.')
        lines+=['','OCORRÊNCIAS DO PERFIL EXPERIMENTAL']
        for occurrence in result['occurrences']:
            direction='acima' if occurrence['direction']=='high' else 'abaixo'
            lines += [f"• {CHANNELS[occurrence['channel']]} {direction} do limiar {occurrence['threshold']} {occurrence['unit']}",
                f"  Regra: {occurrence['rule_id']} | Valores: {occurrence['values']} {occurrence['unit']}",
                f"  Início: {local_time(occurrence['first_timestamp'])} | Fim: {local_time(occurrence['last_timestamp'])}",
                f"  Confirmação: {local_time(occurrence['confirmed_timestamp'])}",
                f"  Índices inclusivos: {occurrence['first_index']}–{occurrence['last_index']} | Confirmação no índice {occurrence['confirmed_index']}",
                f"  Duração de ocupação: {occurrence['duration_seconds']} s | Latência nominal: {occurrence['confirmation_latency_seconds']} s",
                f"  Término: {TERMINATIONS.get(occurrence['termination'],occurrence['termination'])}"]
        if not result['occurrences']:lines.append('Nenhuma ocorrência detectada pelo perfil aplicado. Isso não comprova normalidade.')
        lines+=['','QUALIDADE DOS DADOS']
        for item in result['quality_intervals']:
            lines.append(f"• {CHANNELS[item['channel']]} | índices {item['first_index']}–{item['last_index']} | {QUALITY[item['quality']]} | Motivo: {item['reason']}")
        if not result['quality_intervals']:lines.append('Sem intervalos de qualidade rejeitada registrados.')
        lines+=['','SÉRIE BRUTA: '+{'verified':'verificada — amostras disponíveis na aba Amostras',
            'unavailable':'indisponível — não foi reconstruída',
            'divergent':'divergente ou não verificável — valores não apresentados'}[raw['status']],
            f"Referência da entrada: {raw['reference'] or 'Não disponível'}",
            'Horário e qualidade da entrada só são conferidos contra a série bruta quando ela está verificada.',
            '',f"Evidência: {record['reference']}",f"SHA-256: {record['sha256']}",
            'Consulte o estado atual e o histórico em Alertas e revisão. Gravações exigem cópia de trabalho.']
        blocks.append('\n'.join(lines))
    return '\n\n'.join(blocks)


class MultimodalApp(WorkflowApp):
    def __init__(self,root,**kwargs):
        super().__init__(root,**kwargs)
        self.pending_structured=None
        actions=ttk.Frame(root);actions.pack(fill='x',padx=12,pady=3,before=self.tabs.master)
        self.structured_actions=actions
        ttk.Label(actions,text='Cenário sintético:').pack(side='left')
        self.structured_modality=tk.StringVar(value='Vitais');self.structured_case=tk.StringVar(value='V02')
        kinds=ttk.Combobox(actions,textvariable=self.structured_modality,values=('Vitais','Prescrições','Pausas de áudio'),state='readonly',width=16)
        kinds.pack(side='left',padx=4);kinds.bind('<<ComboboxSelected>>',self.refresh_structured_cases)
        self.structured_choices=ttk.Combobox(actions,textvariable=self.structured_case,state='readonly',width=7)
        self.structured_choices.pack(side='left',padx=4)
        ttk.Button(actions,text='Registrar cenário',command=self.register_structured_scenario).pack(side='left',padx=4)
        ttk.Button(actions,text='Repetir registro pendente',command=self.retry_structured_registration).pack(side='left',padx=4)
        ttk.Label(actions,text='Horários nominais do cenário são preservados.').pack(side='left',padx=6)
        self.last_structured=tk.StringVar(value='Nenhum cenário novo registrado nesta sessão do aplicativo.')
        ttk.Label(root,textvariable=self.last_structured,wraplength=1050).pack(fill='x',padx=12,before=self.tabs.master)
        self.refresh_structured_cases()
        self.sessions.configure(columns=('time','modalities'))
        self.sessions.heading('modalities',text='Modalidades');self.sessions.column('modalities',width=110)
        frame=root.nametowidget(self.tabs.tabs()[2])
        for child in frame.winfo_children():child.destroy()
        nested=ttk.Notebook(frame);nested.pack(fill='both',expand=True)
        vital=ttk.Frame(nested);nested.add(vital,text='Sinais vitais')
        prescriptions=ttk.Frame(nested);nested.add(prescriptions,text='Prescrições')
        self.anomaly_tabs=nested
        prescription_views=ttk.Notebook(prescriptions);prescription_views.pack(fill='both',expand=True)
        prescription_summary=ttk.Frame(prescription_views);prescription_views.add(prescription_summary,text='Resumo e alterações')
        self.prescription_summary=ScrolledText(prescription_summary,wrap='word',font=('Segoe UI',10),padx=10,pady=10)
        self.prescription_summary.pack(fill='both',expand=True)
        versions=ttk.Frame(prescription_views);prescription_views.add(versions,text='Versões antes/depois')
        columns=('side','version','time','item','product','dose','unit','frequency','route','duration','instructions')
        self.prescription_items=ttk.Treeview(versions,columns=columns,show='headings',height=12)
        for col,title,width in zip(columns,['Versão','Número','Emissão local','Item','Produto fictício','Dose','Unidade','Vezes/dia','Via','Dias','Instruções'],[65,55,185,90,110,100,70,70,70,55,240]):
            self.prescription_items.heading(col,text=title);self.prescription_items.column(col,width=width,stretch=False)
        pys=ttk.Scrollbar(versions,orient='vertical',command=self.prescription_items.yview)
        pxs=ttk.Scrollbar(versions,orient='horizontal',command=self.prescription_items.xview)
        self.prescription_items.configure(yscrollcommand=pys.set,xscrollcommand=pxs.set)
        pxs.pack(side='bottom',fill='x');pys.pack(side='right',fill='y');self.prescription_items.pack(fill='both',expand=True)
        views=ttk.Notebook(vital);views.pack(fill='both',expand=True)
        summary=ttk.Frame(views);views.add(summary,text='Resumo e ocorrências')
        self.vitals_summary=ScrolledText(summary,wrap='word',font=('Segoe UI',10),padx=10,pady=10)
        self.vitals_summary.pack(fill='both',expand=True)
        samples=ttk.Frame(views);views.add(samples,text='Amostras')
        cols=('scenario','index','time','channel','value','unit','reported','quality','reason')
        self.samples=ttk.Treeview(samples,columns=cols,show='headings',height=12)
        for col,title,width in zip(cols,['Cenário','Índice','Horário local','Canal','Valor','Unidade','Qualidade informada','Qualidade utilizada','Motivo'],[65,50,185,140,70,65,120,150,160]):
            self.samples.heading(col,text=title);self.samples.column(col,width=width,stretch=False)
        ys=ttk.Scrollbar(samples,orient='vertical',command=self.samples.yview)
        xs=ttk.Scrollbar(samples,orient='horizontal',command=self.samples.xview)
        self.samples.configure(yscrollcommand=ys.set,xscrollcommand=xs.set)
        xs.pack(side='bottom',fill='x');ys.pack(side='right',fill='y');self.samples.pack(fill='both',expand=True)
        self.clear_details()

    def clear_details(self):
        super().clear_details()
        if hasattr(self,'vitals_summary'):
            self.set_text(self.vitals_summary,'Selecione uma sessão para consultar sinais vitais.')
            self.samples.delete(*self.samples.get_children())
        if hasattr(self,'prescription_summary'):
            self.set_text(self.prescription_summary,'Selecione uma sessão para consultar prescrições.')
            self.prescription_items.delete(*self.prescription_items.get_children())

    def load_history(self):
        if self.worker.busy or self.closing:return
        database=self.database.get();patient=self.patient.get()
        token=self.state.begin();self.current_database=None;self.loaded_patient=None
        self.sessions.delete(*self.sessions.get_children());self.clear_details()
        def show(rows):
            if token!=self.state.generation:return
            self.state.rows=rows;self.state.status='ready' if rows else 'empty'
            self.current_database=database;self.loaded_patient=patient
            for row in rows:self.sessions.insert('','end',iid=row.session_id,text=row.session_id,
                values=(local_time(getattr(row,'display_at',row.started_at)),', '.join(row.modalities) or 'Sem eventos'))
            mode='Cópia de trabalho' if self.workspace.is_workspace(database) else 'Consulta histórica — somente leitura'
            self.context.set(mode+' | Áudio, vitais e prescrições | LLM desativada | Sem envio cloud')
            self.status.set(f'{len(rows)} sessão(ões) para {patient} | {mode}' if rows else 'Nenhuma sessão encontrada para este paciente nesta base.')
        self.dispatch(lambda progress:self.reader.sessions(database,patient),show,'Carregando histórico…',lambda code:self.state.fail(token,code))

    def select_session(self,_event=None):
        if self.worker.busy or self.closing:return
        selected=self.sessions.selection()
        if not selected or not self.current_database:return
        database=self.current_database;session=UUID(selected[0]);token=self.state.begin(str(session));self.clear_details()
        def show(detail):
            if not self.state.receive_detail(token,detail):return
            data=detail.document;self.set_text(self.audio,'\n\n'.join('\n'.join(acoustic_lines(x['evidence'])) for x in data['acoustics']) if data.get('acoustics') else audio_text(detail));self.set_text(self.vitals_summary,vital_text(detail))
            self.set_text(self.prescription_summary,prescription_text(detail))
            for record in data.get('prescriptions',[]):
                for side,title in [('before','Antes'),('after','Depois')]:
                    snapshot=record['evidence']['result'][side]
                    for item in snapshot['items']:
                        self.prescription_items.insert('','end',values=(title,snapshot['version'],local_time(snapshot['issued_at']),
                            item['item_id'],item['product_code'],item['dose_value'],item['dose_unit'],item['frequency_per_day'],
                            item['route'],item['duration_days'],item['instructions']))
            for record in data['vitals']:
                for sample in record['raw_series']['samples']:
                    value='Não disponível' if sample['value'] is None else str(sample['value'])
                    self.samples.insert('','end',values=(record['evidence']['scenario_id'],sample['index'],local_time(sample['timestamp']),
                        CHANNELS[sample['channel']],value,sample['unit'],QUALITY[sample['reported_quality']],QUALITY[sample['quality']],sample['reason'] or '—'))
            for row in data['events']:
                event=row['event'];item=row['evidence_item'];kind=item.get('term','Resumo técnico')
                if row['modality']=='vitals':kind=('Ocorrência' if 'rule_id' in item else 'Qualidade' if 'quality' in item else 'Resumo de vitais')
                if row['modality']=='prescriptions':kind=('Divergência do plano sintético' if '&item=/expectation_candidates/' in event['evidence_ref'] else CHANGES.get(item.get('kind'),'Resumo de prescrições'))
                if row['modality']=='acoustics':kind='Pausas frequentes — experimental' if '&item=/candidates/' in event['evidence_ref'] else 'Resumo acústico'
                prefix={'vitals':'Vitais ','prescriptions':'Prescrições ','audio':'Áudio ','acoustics':'Pausas '}[row['modality']]
                self.events.insert('','end',iid=event['event_id'],text=prefix+event['event_id'],
                    values=(label(event['review_status']),kind))
            if data['vitals']:self.tabs.select(self.anomaly_tab);self.anomaly_tabs.select(0)
            if data.get('prescriptions'):self.tabs.select(self.anomaly_tab);self.anomaly_tabs.select(1)
            if data.get('acoustics'):self.tabs.select(self.audio_tab)
            self.status.set('Evidência de vitais verificada. Gravações exigem cópia de trabalho.' if data['vitals'] else
                'Evidência de prescrições verificada. Gravações exigem cópia de trabalho.' if data.get('prescriptions') else
                'Evidência acústica verificada; sem ASR ou LLM.' if data.get('acoustics') else 'Evidência de áudio verificada.' if data['documents'] else 'Sem eventos suportados nesta sessão.')
            if data['unsupported_sources']:self.status.set(self.status.get()+' Há modalidade com integração pendente.')
        self.dispatch(lambda progress:self.reader.detail(database,session),show,'Carregando evidência…',lambda code:self.state.fail(token,code))

    def submit_review(self,target):
        selected=self.events.selection()
        if selected and self.state.detail:
            row=next(r for r in self.state.detail.document['events'] if r['event']['event_id']==selected[0])
            if row['modality']!='audio' and not getattr(self.workspace,'supports_structured',False):
                name='Vitais' if row['modality']=='vitals' else 'Prescrições'
                self.status.set(name+': somente consulta. Revisão desta modalidade será habilitada na tarefa 4.');return
        super().submit_review(target)

    def refresh_structured_cases(self,_event=None):
        modality={'Vitais':'vitals','Prescrições':'prescriptions','Pausas de áudio':'acoustics'}[self.structured_modality.get()]
        values=self.workspace.scenarios(modality) if getattr(self.workspace,'supports_structured',False) else ()
        self.structured_choices.configure(values=values)
        if self.structured_case.get() not in values:self.structured_case.set(values[0] if values else '')

    def register_structured_scenario(self):
        if self.worker.busy or not self._require_workspace():return
        if not getattr(self.workspace,'supports_structured',False):
            self.status.set('Esta instância permite apenas consulta das modalidades estruturadas.');return
        if self.pending_structured:
            self.status.set('Há uma gravação pendente. Use Repetir registro pendente antes de iniciar outra execução.');return
        database=self.current_database;patient=self.loaded_patient;scenario=self.structured_case.get()
        modality={'Vitais':'vitals','Prescrições':'prescriptions','Pausas de áudio':'acoustics'}[self.structured_modality.get()]
        if scenario not in self.workspace.scenarios(modality):
            self.status.set('Selecione um cenário válido.');return
        if not messagebox.askyesno('Registrar cenário sintético',
            f'Modalidade: {self.structured_modality.get()}\nCenário: {scenario}\nPaciente fictício: {patient}\n'+
            ('Analisar pausas localmente e registrar uma nova execução? Horário de processamento; sem ASR/LLM.\n' if modality=='acoustics' else 'Registrar uma nova execução na cópia de trabalho, preservando os horários nominais do cenário?\n')+
            'Não há dados clínicos reais ou chamada LLM nesta operação.',parent=self.root):return
        self.pending_structured=None
        def ready(result):
            if result.persisted:
                self.last_structured.set(f'{result.scenario} registrado. Nova sessão: {result.session_id} | Base: {database}')
                self.load_history()
            else:
                self.pending_structured=(database,result.run_id)
                self.last_structured.set('Gravação não confirmada. '+ERRORS.get(result.error_code,ERRORS['structured_persistence_failed']))
                self.status.set('Use Repetir registro pendente para reutilizar os bytes preparados, sem nova execução.')
        self.dispatch(lambda progress:self.workspace.register_scenario(database,patient,modality,scenario,progress),
            ready,'Conferindo e registrando cenário sintético…')

    def retry_structured_registration(self):
        if self.worker.busy or not self._require_workspace():return
        if not self.pending_structured or self.pending_structured[0]!=self.current_database:
            self.status.set(ERRORS['no_pending_registration']);return
        database,run_id=self.pending_structured
        def ready(result):
            self.pending_structured=None
            self.last_structured.set(f'Gravação confirmada para {result.scenario}. Sessão: {result.session_id}. Mesmos bytes e IDs reutilizados.')
            self.load_history()
        self.dispatch(lambda progress:self.workspace.retry_structured(database,run_id),ready,'Repetindo somente a gravação preparada…')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--database');parser.add_argument('--patient',default='PAT-001')
    parser.add_argument('--ui',choices=('custom','simplified','classic'),default='custom',help='Aparência CustomTkinter, simplificada nativa ou interface clássica nativa')
    args=parser.parse_args(argv);project=Path(__file__).resolve().parents[2]
    from medassistmultimodal.desktop_simplified import SimplifiedApp
    from medassistmultimodal.desktop_text import TextHistoryReader,TextWorkspace
    if args.ui=='custom':
        try:
            import customtkinter as ctk
            from medassistmultimodal.desktop_custom import CustomApp,configure_appearance,OpaqueCTk
        except ImportError:
            parser.error('CustomTkinter indisponível neste ambiente. Use --ui simplified ou instale requirements-ui.txt no ambiente do projeto.')
        configure_appearance();root=OpaqueCTk();app_type=CustomApp
    else:
        from medassistmultimodal.desktop_summary import SummaryApp
        root=tk.Tk();app_type=SimplifiedApp if args.ui=='simplified' else SummaryApp
    app=app_type(root,reader=TextHistoryReader(project),workspace=TextWorkspace(project),project_root=project)
    app.patient.set(args.patient)
    if args.database:app.database.set(args.database);root.after(0,app.load_history)
    root.mainloop()


if __name__=='__main__':main()
