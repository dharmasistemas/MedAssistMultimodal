"""Readable audio results and explicit local listening for the simplified shell."""
import time
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from medassistmultimodal.desktop import label
from medassistmultimodal.application.desktop_history import HistoryError
from medassistmultimodal.infrastructure.audio_playback import WindowsAudioPlayer, PlaybackError, playback_source, prepare_listening_audio


def audio_result_text(detail):
    data = detail.document
    if data.get('acoustics'):
        blocks = []
        states = {'signal':'Padrão experimental de pausas frequentes — requer revisão.',
                  'no_signal':'Sem sinal do perfil de pausas; não comprova normalidade.',
                  'insufficient_evidence':'Evidência acústica insuficiente.'}
        for record in data['acoustics']:
            doc = record['evidence']; assessment = doc['assessment']
            fraction = assessment['long_pause_fraction']
            fraction = 'indisponível' if fraction is None else f'{fraction:.1%}'
            blocks.append('\n'.join([f"Áudio {doc['input']['case_id']} · voz sintética · integridade verificada",
                states[assessment['status']], f"Pausas longas: {assessment['long_pause_count']} · fração central: {fraction}",
                'Sem transcrição ou LLM nesta análise. Piloto técnico; não detecta condição médica.',
                'Os intervalos calculados e o critério completo estão na evidência técnica.']))
        return '\n\n'.join(blocks)
    blocks = []
    for record in data.get('documents', []):
        doc = record['evidence']
        asr, rules, llm = doc['asr'], doc['rules'], doc['llm']
        transcript = asr.get('result')
        filename = doc['input']['audio_ref'].replace('\\','/').rsplit('/',1)[-1]
        lines = [f"Áudio: {filename}", f"Integridade verificada · {label(doc['summary']['status'])}",
                 f"Origem: {label(doc['input']['origin_kind'])} · relato fictício, independente do vídeo.",
                 '', 'TRANSCRIÇÃO', transcript['text'] if transcript else 'Transcrição indisponível. Estado: '+label(asr['status']),
                 '', 'MENÇÕES E CONTEXTO — REGRAS LOCAIS']
        contexts = {'affirmed_current':'relato atual afirmado', 'negated_current':'negado no relato atual',
                    'affirmed_historical':'relato histórico', 'affirmed_earlier_in_session':'relatado antes na sessão',
                    'conditional':'condicional', 'third_party':'relato de terceiro', 'unknown':'contexto incerto'}
        for item in rules.get('items') or []:
            context = contexts.get(item['context'], item['context'])
            review = ' · candidato à revisão humana' if item['classification'] == 'candidate_for_human_review' else ''
            lines.append(f"• {item['term']} · {context}{review}\n  {item['sentence']}")
        if not rules.get('items'):
            lines.append('Nenhuma menção configurada encontrada.' if rules['status'] == 'succeeded_no_mentions'
                         else 'Menções indisponíveis. Estado: '+label(rules['status']))
        lines += ['', 'ANÁLISE TEXTUAL OPCIONAL — NÃO DECIDE ALERTAS']
        result = llm.get('result')
        if result:
            sentiments = {'positive':'Positivo','negative':'Negativo','mixed':'Misto','neutral':'Neutro','unknown':'Indeterminado'}
            lines.append('Sentimento do texto: '+sentiments.get(result['sentiment'], result['sentiment']))
            lines += ['• '+item['quote'] for item in result.get('sentiment_evidence', [])]
            lines += [f"• Termo: {item['term']} — {item['evidence']['quote']}" for item in result.get('terms', [])]
            lines.append('Sentimento textual não é emoção vocal, diagnóstico ou urgência. Uma resposta válida pode omitir informações.')
        else:
            lines.append('Estado desta execução: '+label(llm['status']))
        lines += ['', 'Confira evidência e revisão humana. Ausência de menção não comprova ausência de problema clínico.']
        blocks.append('\n'.join(lines))
    return '\n\n'.join(blocks) or 'Esta sessão não contém análise de áudio. Selecione um resultado de áudio ou pausas.'


class AudioPanel:
    def __init__(self, app, player=None):
        self.app = app
        self.player = player or WindowsAudioPlayer()
        self.loaded_path = None
        self.prepared = None
        self.generation = 0
        self.last_poll = 0.
        self.pilot = tk.BooleanVar(value=False)
        self.kind = tk.StringVar(value='Relato e transcrição')
        for child in app.audio_tab.pack_slaves():
            child.pack_forget()
        self.frame = ttk.Frame(app.audio_tab, padding=10)
        self.frame.pack(fill='both', expand=True)
        self.frame.columnconfigure(1, weight=1)
        self.frame.rowconfigure(0, weight=1)
        host = ttk.Frame(self.frame)
        host.grid(row=0, column=0, sticky='ns')
        host.rowconfigure(0, weight=1)
        canvas = tk.Canvas(host, width=260, height=1, highlightthickness=0)
        canvas.grid(row=0, column=0, sticky='ns')
        scrollbar = ttk.Scrollbar(host, orient='vertical', command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky='ns')
        canvas.configure(yscrollcommand=scrollbar.set)
        inputs = ttk.Frame(canvas, padding=(0,0,10,0))
        window = canvas.create_window(0, 0, anchor='nw', window=inputs, width=260)
        inputs.bind('<Configure>', lambda event: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda event: canvas.itemconfigure(window, width=event.width))
        ttk.Label(inputs, text='Entrada', font=('Segoe UI',11,'bold')).pack(anchor='w')
        kind = ttk.Combobox(inputs, textvariable=self.kind, values=('Relato e transcrição','Pausas de áudio (piloto)'), state='readonly', width=26)
        kind.pack(fill='x', pady=6)
        kind.bind('<<ComboboxSelected>>', self.choose_kind)
        ttk.Label(inputs, text='Áudio de demonstração').pack(anchor='w')
        try:
            cases = app.workspace.clips()
        except HistoryError:
            cases = ()
        self.choices = ttk.Combobox(inputs, textvariable=app.case, values=cases, state='readonly', width=26)
        self.choices.pack(fill='x', pady=5)
        if cases and app.case.get() not in cases:
            app.case.set(cases[0])
        self.origin = tk.StringVar(value='Áudios fictícios autorizados. Voz independente do participante do vídeo.')
        ttk.Label(inputs, textvariable=self.origin, wraplength=245).pack(anchor='w', pady=5)
        ttk.Label(inputs, text='Ouvir antes de processar', font=('Segoe UI',10,'bold')).pack(anchor='w', pady=(8,3))
        playback = ttk.Frame(inputs); playback.pack(fill='x')
        ttk.Button(playback, text='Ouvir', command=self.play).pack(side='left')
        ttk.Button(playback, text='Pausar', command=self.pause).pack(side='left', padx=4)
        ttk.Button(playback, text='Parar', command=self.stop).pack(side='left')
        self.clock = tk.StringVar(value='00:00 / 00:00 · parado')
        ttk.Label(inputs, textvariable=self.clock).pack(anchor='w', pady=4)
        self.progress = ttk.Progressbar(inputs, mode='determinate', maximum=1)
        self.progress.pack(fill='x', pady=(0,8))
        app.cloud_check = ttk.Checkbutton(inputs, text='Incluir análise textual\ncom GPT-OSS (cloud)', variable=app.use_cloud_text)
        app.cloud_check.pack(anchor='w', pady=5)
        ttk.Label(inputs, text='Opcional, com confirmação por execução. Envia somente a transcrição fictícia. LLM não decide alertas.', wraplength=245).pack(anchor='w')
        self.options = ttk.Frame(inputs)
        ttk.Label(self.options, text='Horário da sessão com fuso').pack(anchor='w')
        ttk.Entry(self.options, textvariable=app.session_at, width=27).pack(fill='x', pady=3)
        ttk.Button(self.options, text='Criar cópia de trabalho', command=app.create_workspace).pack(fill='x', pady=3)
        self.options_open = False
        ttk.Button(inputs, text='Opções de processamento ▸', command=self.toggle_options).pack(fill='x', pady=8)
        self.process_button = ttk.Button(inputs, text='Processar áudio', command=app.process_audio)
        self.process_button.pack(fill='x', pady=3)
        ttk.Button(inputs, text='Repetir gravação pendente', command=self.retry).pack(fill='x', pady=3)
        ttk.Button(inputs, text='Revisar resultado', command=app.open_review).pack(fill='x', pady=6)

        result = ttk.Frame(self.frame, padding=(12,0,0,0))
        result.grid(row=0, column=1, sticky='nsew')
        result.columnconfigure(0, weight=1); result.rowconfigure(2, weight=1)
        ttk.Label(result, text='Resultados já processados', font=('Segoe UI',11,'bold')).grid(row=0,column=0,sticky='w')
        self.history_value = tk.StringVar()
        self.history = ttk.Combobox(result, textvariable=self.history_value, state='readonly', width=25)
        self.history.grid(row=1,column=0,sticky='ew',pady=6)
        self.history.bind('<<ComboboxSelected>>', self.select_history)
        self.history_ids = {}
        self.result = ScrolledText(result, wrap='word', width=30, height=15, font=('Segoe UI',10), padx=10,pady=10)
        self.result.grid(row=2,column=0,sticky='nsew')
        app.set_text(self.result,'Consulte a base para listar resultados de áudio. Escolha uma entrada à esquerda para ouvir ou criar uma nova execução.')
        ttk.Button(result, text='Evidência técnica ▸', command=self.toggle_technical).grid(row=3,column=0,sticky='w',pady=5)
        self.technical = ttk.Frame(result)
        app.audio.frame.pack(in_=self.technical, fill='both', expand=True)
        app.audio.frame.lift()
        app.audio.configure(height=6, width=30)
        self.technical_open = False
        self.case_trace = app.case.trace_add('write', lambda *args: self.input_changed())

    def choose_kind(self, _event=None):
        self.pilot.set(self.kind.get() == 'Pausas de áudio (piloto)')
        self.stop()
        try:
            cases = self.app.workspace.scenarios('acoustics') if self.pilot.get() else self.app.workspace.clips()
        except HistoryError:
            cases = ()
            self.app.status.set('Catálogo de áudio indisponível.')
        self.choices.configure(values=cases)
        if self.app.case.get() not in cases:
            self.app.case.set(cases[0] if cases else '')
        if self.pilot.get():
            self.app.use_cloud_text.set(False)
        self.app.cloud_check.configure(state='disabled' if self.pilot.get() else 'normal')
        self.origin.set('Piloto acústico sintético. Sem ASR/LLM; não demonstra condição médica.' if self.pilot.get()
                        else 'Áudios fictícios autorizados. Voz independente do participante do vídeo.')

    def input_changed(self):
        self.stop()

    def play(self):
        if self.app.worker.busy or self.app.closing:
            return
        try:
            path = playback_source(self.app.project_root,self.app.case.get(),pilot=self.pilot.get())
            if path == self.loaded_path:
                self.player.play(); self.update_player()
                return
            requested = (self.app.case.get(),self.pilot.get())
            token = None
            def ready(prepared):
                if token != self.generation or requested != (self.app.case.get(),self.pilot.get()):
                    prepared.close()
                    return
                self.prepared = prepared
                try:
                    self.player.open(prepared.path)
                    self.loaded_path = path
                    self.player.play(); self.update_player()
                    self.app.status.set('Escuta local do áudio selecionado. Nenhum ASR/LLM executado.')
                except PlaybackError:
                    self.stop(); self.clock.set('Reprodução local indisponível. Processamento permanece independente.')
            def failed(code):
                self.clock.set('Não foi possível preparar a escuta local.')
            def prepare(progress):
                source = playback_source(self.app.project_root,requested[0],pilot=requested[1])
                prepared = prepare_listening_audio(source)
                try:
                    playback_source(self.app.project_root,requested[0],pilot=requested[1])
                except PlaybackError:
                    prepared.close()
                    raise
                return prepared
            self.app.dispatch(prepare,ready,'Preparando escuta local…',failed)
            token = self.generation
        except PlaybackError as exc:
            self.stop()
            self.clock.set(str(exc))

    def pause(self):
        try:
            self.player.pause(); self.update_player()
        except PlaybackError:
            self.stop(); self.clock.set('Falha na reprodução local; processamento permanece independente.')

    def stop(self):
        self.generation += 1
        try:
            self.player.close()
        except PlaybackError:
            self.clock.set('Não foi possível liberar o reprodutor local.')
            return
        self.loaded_path = None
        if self.prepared is not None:
            self.prepared.close()
            self.prepared = None
        self.clock.set('00:00 / 00:00 · parado')
        self.progress.configure(value=0)

    def update_player(self):
        position, mode = self.player.status()
        def clock(ms):
            seconds = ms//1000
            return f'{seconds//60:02d}:{seconds%60:02d}'
        self.progress.configure(maximum=max(1,self.player.duration_ms),value=position)
        states={'playing':'reproduzindo','paused':'pausado','stopped':'parado','closed':'parado'}
        self.clock.set(f'{clock(position)} / {clock(self.player.duration_ms)} · {states.get(mode,"parado")}')

    def poll(self):
        if time.monotonic()-self.last_poll < .25 or self.loaded_path is None:
            return
        self.last_poll = time.monotonic()
        try:
            self.update_player()
        except PlaybackError:
            self.stop(); self.clock.set('Reprodução indisponível. Você pode continuar sem escuta.')

    def toggle_options(self):
        self.options_open = not self.options_open
        if self.options_open:
            self.options.pack(fill='x', before=self.process_button)
        else:
            self.options.pack_forget()

    def toggle_technical(self):
        self.technical_open = not self.technical_open
        if self.technical_open:
            self.technical.grid(row=4,column=0,sticky='ew')
        else:
            self.technical.grid_remove()

    def retry(self):
        if self.pilot.get():
            self.app.retry_structured_registration()
        else:
            self.app.retry_process()

    def populate_history(self, rows):
        from medassistmultimodal.desktop import local_time
        self.history_ids = {f'{index+1} · {local_time(getattr(row,'display_at',row.started_at))} · {", ".join(row.modalities)}':row.session_id
                            for index,row in enumerate(rows) if 'Áudio' in row.modalities or 'audio' in row.modalities or 'acoustics' in row.modalities or 'Pausas de áudio' in row.modalities}
        self.history.configure(values=tuple(self.history_ids))

    def clear_history(self):
        self.history_ids = {}; self.history_value.set(''); self.history.configure(values=())

    def select_history(self, _event=None):
        sid = self.history_ids.get(self.history_value.get())
        if sid:
            self.app.sessions.selection_set(sid)
            self.app.select_session()
