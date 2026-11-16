"""Factual structured-data presentation; no inference or alert decisions here."""
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from medassistmultimodal.desktop import local_time
from medassistmultimodal.desktop_multimodal import CHANNELS, PRESCRIPTION_FIELDS, CHANGES
from medassistmultimodal.application.prescription_expectation_text import REASONS


def anomaly_result_text(detail):
    data = detail.document
    blocks = []
    timing = [f"Registro no aplicativo: {local_time(data['registered_at'])}" if data.get('registered_at') else 'Registro no aplicativo: não disponível na auditoria.',
              f"Horário nominal do cenário: {local_time(data['session']['started_at'])}"]
    for record in data.get('vitals', []):
        doc = record['evidence']; result = doc['result']
        occurrences = result['occurrences']
        lines = ['SINAIS VITAIS · integridade da evidência verificada',
                 f"Cenário {doc['scenario_id']} · paciente fictício {doc['subject']['patient_id']}",
                 f"Regra local com persistência de {result['persistence']} amostras consecutivas.", '']
        if occurrences:
            lines.append(f'{len(occurrences)} ocorrência(s) do perfil experimental — requerem revisão.')
            for occurrence in occurrences:
                direction = 'acima' if occurrence['direction'] == 'high' else 'abaixo'
                lines += [f"• {CHANNELS[occurrence['channel']]} {direction} de {occurrence['threshold']} {occurrence['unit']}",
                          f"  Valores: {occurrence['values']} {occurrence['unit']}",
                          f"  Período nominal: {local_time(occurrence['first_timestamp'])} até {local_time(occurrence['last_timestamp'])}"]
        else:
            lines.append('Nenhuma ocorrência deste perfil. Isso não comprova normalidade.')
        unavailable = [CHANNELS[c['channel']] for c in result['coverage'] if c['valid_samples'] == 0]
        if unavailable:
            lines.append('Sem dados válidos nos canais: '+', '.join(unavailable)+'.')
        if result['quality_intervals']:
            lines.append(f"Há {len(result['quality_intervals'])} intervalo(s) com limitações de qualidade; consulte os dados antes de interpretar o resultado.")
        if record['raw_series']['status'] != 'verified':
            lines.append('Amostras brutas indisponíveis ou não verificadas; não foram reconstruídas.')
        lines += ['', 'Dados sintéticos de cenário de internação; independentes do vídeo e das vozes.',
                  'Regras determinísticas, sem LLM. Não realizam diagnóstico.']
        blocks.append('\n'.join(lines))
    for record in data.get('prescriptions', []):
        doc = record['evidence']; result = doc['result']; expectation = doc.get('expectation')
        lines = ['PRESCRIÇÕES · integridade da evidência verificada',
                 f"Paciente fictício {result['patient_id']} · versões {result['before']['version']} → {result['after']['version']}",
                 f"Incluídos: {result['included_count']} · removidos: {result['removed_count']} · modificados: {result['modified_count']}", '']
        if expectation:
            titles = {'compatible':'Compatível com o plano sintético declarado.',
                      'divergent':'Divergência do plano sintético — requer revisão.',
                      'indeterminate':'Expectativa indeterminada — não foi possível concluir a comparação com o plano.'}
            lines += [titles[expectation['status']], REASONS[expectation['reason']]]
            for difference in expectation['differences']:
                field = PRESCRIPTION_FIELDS.get(difference['field'], 'Presença do item' if difference['field']=='presence' else difference['field'])
                def value(v):
                    return {'present':'presente','absent':'ausente'}.get(v,v) if isinstance(v,str) else v
                lines.append(f"• {difference['item_id']} · {field}: esperado {value(difference['expected'])}; observado {value(difference['observed'])}")
        else:
            lines += ['Expectativa não avaliada nesta comparação histórica.',
                      'Diferença entre versões não comprova alteração inesperada ou erro terapêutico.']
        for change in result['changes']:
            lines.append(f"• {change['item_id']}: {CHANGES[change['kind']]}")
            for side, title in (('before','Antes'),('after','Depois')):
                item = change[side]
                if item is not None:
                    lines.append(f"  {title}: {item['product_code']} · {item['dose_value']} {item['dose_unit']} · {item['frequency_per_day']}/dia · {item['route']} · {item['duration_days']} dias")
                else:
                    lines.append(f'  {title}: item ausente.')
            for field in change['field_changes']:
                lines.append(f"  {PRESCRIPTION_FIELDS[field['field']]}: {field['before']} → {field['after']}")
            if change['unit_change_note']:
                lines.append('  Mudança de unidade: equivalência clínica não interpretada.')
        lines += ['', 'Dados sintéticos. Comparação determinística, sem LLM.',
                  'Não determina segurança terapêutica nem recomenda tratamento. Versões completas e plano estão nos detalhes.']
        blocks.append('\n'.join(lines))
    return ('\n'.join(timing)+'\n\n'+'\n\n'.join(blocks)) if blocks else 'Esta sessão não contém sinais vitais ou prescrições. Selecione um resultado dessas modalidades.'


class AnomalyPanel:
    def __init__(self, app):
        self.app = app
        for child in app.anomaly_tab.pack_slaves():
            child.pack_forget()
        self.frame = ttk.Frame(app.anomaly_tab, padding=10)
        self.frame.pack(fill='both', expand=True)
        self.frame.columnconfigure(1, weight=1); self.frame.rowconfigure(0, weight=1)
        host = ttk.Frame(self.frame); host.grid(row=0,column=0,sticky='ns'); host.rowconfigure(0,weight=1)
        canvas = tk.Canvas(host, width=250,height=1,highlightthickness=0)
        canvas.grid(row=0,column=0,sticky='ns')
        scroll = ttk.Scrollbar(host,orient='vertical',command=canvas.yview); scroll.grid(row=0,column=1,sticky='ns')
        canvas.configure(yscrollcommand=scroll.set)
        inputs = ttk.Frame(canvas,padding=(0,0,10,0))
        window = canvas.create_window(0,0,anchor='nw',window=inputs,width=250)
        inputs.bind('<Configure>',lambda event:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda event:canvas.itemconfigure(window,width=event.width))
        ttk.Label(inputs,text='Entrada',font=('Segoe UI',11,'bold')).pack(anchor='w')
        ttk.Label(inputs,text='Dados a analisar').pack(anchor='w',pady=(10,3))
        self.kinds = ttk.Combobox(inputs,textvariable=app.structured_modality,values=('Vitais','Prescrições'),state='readonly',width=25)
        self.kinds.pack(fill='x'); self.kinds.bind('<<ComboboxSelected>>',app.refresh_structured_cases)
        ttk.Label(inputs,text='Cenário de demonstração').pack(anchor='w',pady=(12,3))
        app.structured_choices = ttk.Combobox(inputs,textvariable=app.structured_case,state='readonly',width=25)
        app.structured_choices.pack(fill='x')
        app.refresh_structured_cases()
        self.origin = tk.StringVar()
        self.update_origin()
        ttk.Label(inputs,textvariable=self.origin,wraplength=235).pack(anchor='w',pady=15)
        ttk.Label(inputs,text='Análise por regras locais.\nSem chamada de LLM.',wraplength=235).pack(anchor='w')
        ttk.Button(inputs,text='Analisar cenário',command=app.register_structured_scenario).pack(fill='x',pady=(14,4))
        ttk.Button(inputs,text='Repetir registro pendente',command=app.retry_structured_registration).pack(fill='x',pady=4)
        ttk.Button(inputs,text='Revisar resultado',command=app.open_review).pack(fill='x',pady=8)
        ttk.Label(inputs,text='Movimentação durante internação:\nnão demonstrada neste projeto.',wraplength=235).pack(anchor='w',pady=12)
        result = ttk.Frame(self.frame,padding=(12,0,0,0)); result.grid(row=0,column=1,sticky='nsew')
        result.columnconfigure(0,weight=1); result.rowconfigure(2,weight=1,minsize=90)
        ttk.Label(result,text='Resultados já processados',font=('Segoe UI',11,'bold')).grid(row=0,column=0,sticky='w')
        self.history_value = tk.StringVar(); self.history_ids = {}
        self.history = ttk.Combobox(result,textvariable=self.history_value,state='readonly',width=25)
        self.history.grid(row=1,column=0,sticky='ew',pady=6); self.history.bind('<<ComboboxSelected>>',self.select_history)
        self.result = ScrolledText(result,wrap='word',width=30,height=15,font=('Segoe UI',10),padx=10,pady=10)
        self.result.grid(row=2,column=0,sticky='nsew')
        app.set_text(self.result,'Consulte a base para listar resultados de vitais e prescrições. A entrada define a próxima análise.')
        ttk.Button(result,text='Dados, critérios e evidência ▸',command=self.toggle_technical).grid(row=3,column=0,sticky='w',pady=5)
        self.technical = ttk.Frame(result)
        app.anomaly_tabs.configure(height=170,width=30)
        app.anomaly_tabs.pack(in_=self.technical,fill='both',expand=True)
        app.anomaly_tabs.lift()
        ttk.Label(self.technical,textvariable=app.last_structured,wraplength=500).pack(fill='x')
        self.technical_open = False

    def update_origin(self):
        self.origin.set(f'{self.app.patient.get()} · paciente fictício\nDados sintéticos de cenário de internação, independentes do vídeo e dos locutores.')

    def toggle_technical(self):
        self.technical_open = not self.technical_open
        if self.technical_open:
            self.technical.grid(row=4,column=0,sticky='ew')
        else:
            self.technical.grid_remove()

    def clear(self):
        self.history_value.set('')
        self.app.set_text(self.result,'Selecione um resultado verificado de vitais ou prescrições. A entrada define a próxima análise.')

    def clear_history(self):
        self.history_ids = {}; self.history_value.set(''); self.history.configure(values=())

    def populate_history(self,rows):
        selected = [row for row in rows if {'Vitais','Prescrições'}.intersection(row.modalities)]
        self.history_ids = {f'{index+1} · {", ".join(row.modalities)} · {local_time(getattr(row,'display_at',row.started_at))}':row.session_id
                            for index,row in enumerate(selected)}
        self.history.configure(values=tuple(self.history_ids))

    def show(self,detail):
        self.app.set_text(self.result,anomaly_result_text(detail))
        sid = detail.document['session']['session_id']
        self.history_value.set(next((name for name,value in self.history_ids.items() if value == sid),''))

    def select_history(self,_event=None):
        sid = self.history_ids.get(self.history_value.get())
        if sid:
            self.app.sessions.selection_set(sid); self.app.select_session()
