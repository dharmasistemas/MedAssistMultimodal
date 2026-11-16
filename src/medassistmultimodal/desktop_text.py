"""Optional cloud text analysis for new fictional audio runs; controls live in Audio."""
from datetime import datetime
import json
from tkinter import ttk,messagebox
import tkinter as tk

from medassistmultimodal.desktop_video import VideoApp
from medassistmultimodal.desktop import audio_text,label,LABELS
from medassistmultimodal.desktop_workflow import ERRORS
from medassistmultimodal.infrastructure.desktop_text import TextWorkspace,TextHistoryReader

LABELS.update(unavailable='Indisponível',invalid_response='Resposta inválida',
    unsupported_input='Entrada fora dos limites',not_configured='Não configurada',not_run='Não executada')

ERRORS['cloud_text_authorization_required']='Confirme explicitamente o envio da transcrição fictícia antes de usar GPT-OSS.'
SENTIMENT={'positive':'Positivo','negative':'Negativo','mixed':'Misto','neutral':'Neutro','unknown':'Indeterminado'}


def optional_audio_text(detail):
    if detail.document.get('acoustics'):
        from medassistmultimodal.application.register_acoustics import acoustic_lines
        blocks=[]
        for record in detail.document['acoustics']:
            doc=record['evidence'];lines=acoustic_lines(doc)
            lines+=['','INTERVALOS DE BAIXA ENERGIA (descritores a partir de 0,20 s)',
                'Incluem intervalos curtos e bordas; não equivalem à contagem de pausas longas internas do perfil.']
            for interval in doc['features']['low_energy_intervals']:
                a=interval['start_seconds'];b=interval['end_seconds']
                lines.append(f'• {a:.3f}–{b:.3f} s | duração {b-a:.3f} s')
            if not doc['features']['low_energy_intervals']:lines.append('Nenhum intervalo descrito.')
            blocks.append('\n'.join(lines))
        return '\n\n'.join(blocks)
    text=audio_text(detail)
    for record in detail.document['documents']:
        llm=record['evidence']['llm'];result=llm.get('result')
        if not result:continue
        lines=[f"Sentimento textual: {SENTIMENT.get(result['sentiment'],result['sentiment'])}",
            'O sentimento descreve o texto; não é emoção vocal, diagnóstico ou urgência.',
            f"Fonte: {result['source']} | Modelo: {result['model']}",
            f"Prompt: {llm.get('prompt_revision','Versão anterior')} | Contrato: {result['protocol_version']}",
            '', 'Citações que sustentam o sentimento:']
        lines += ['• '+e['quote'] for e in result['sentiment_evidence']] or ['Sem evidência; resultado indeterminado.']
        lines += ['', 'Termos extraídos pela LLM (não decidem alertas):']
        lines += [f"• {e['term']}: {e['evidence']['quote']}" for e in result['terms']] or ['Nenhum termo extraído pela LLM.']
        lines += ['', 'Uma resposta válida pode omitir informações. Confira a transcrição e as regras.']
        text=text.replace(json.dumps(result,ensure_ascii=False,indent=2),'\n'.join(lines),1)
    return text


class TextAudioApp(VideoApp):
    def __init__(self,root,**kwargs):
        super().__init__(root,**kwargs)
        self.use_cloud_text=tk.BooleanVar(value=False)
        audio_frame=root.nametowidget(self.tabs.tabs()[0])
        controls=ttk.Frame(audio_frame);controls.pack(fill='x',padx=8,pady=6,before=self.audio.frame)
        self.cloud_check=ttk.Checkbutton(controls,text='Análise textual opcional: GPT-OSS 120B (Ollama cloud)',variable=self.use_cloud_text)
        self.cloud_check.pack(anchor='w')
        ttk.Label(controls,text='Aplica-se ao próximo processamento de áudio. Envia somente a transcrição fictícia, sem áudio.\n'
            'LLM não decide alertas. Desmarcado: Whisper e regras locais, sem envio cloud.',wraplength=650).pack(anchor='w')

    def _set_busy(self,busy):
        super()._set_busy(busy)
        if hasattr(self,'cloud_check'):self.cloud_check.configure(state='disabled' if busy else 'normal')

    def poll(self):
        super().poll()
        # Label describes the selected option, not the historical execution currently displayed.
        if hasattr(self,'use_cloud_text') and not self.closing:
            mode='Cópia de trabalho' if self.current_database and self.workspace.is_workspace(self.current_database) else 'Consulta histórica'
            self.context.set(mode+' | Próximo áudio: '+('GPT-OSS cloud opcional habilitado; exige confirmação' if self.use_cloud_text.get() else 'LLM desativada, sem envio cloud'))

    def select_session(self,_event=None):
        if self.worker.busy or self.closing:return
        super().select_session(_event)
        if self.worker.busy and self.on_success is not None:
            original=self.on_success
            def show(detail):
                original(detail)
                if self.state.detail is detail:self.set_text(self.audio,optional_audio_text(detail))
            self.on_success=show

    def process_audio(self):
        if self.worker.busy or not self._require_workspace():return
        enabled=self.use_cloud_text.get()
        if not enabled:return super().process_audio()
        try:
            session_at=datetime.fromisoformat(self.session_at.get())
            if session_at.tzinfo is None or session_at.utcoffset() is None:raise ValueError()
        except ValueError:self.status.set('Informe data/hora ISO8601 com fuso.');return
        database=self.current_database;patient=self.loaded_patient;case=self.case.get()
        if not messagebox.askyesno('Confirmar análise textual em nuvem',
            f'Áudio simulado: {case} | Paciente fictício: {patient}\n'
            'Executar Whisper local e enviar SOMENTE sua transcrição ao GPT-OSS 120B pelo Ollama cloud?\n'
            'Será usada sua conta Ollama conectada. Não haverá compra de créditos ou troca de plano.\n'
            'Regras locais independem da LLM. Falhas da LLM não serão repetidas automaticamente.\n'
            'Esta ação cria uma nova execução e não modifica sessões anteriores.',parent=self.root):return
        self.pending_process=None
        def ready(result):
            if not result.persisted:
                self.pending_process=(database,result.run_id)
                self.status.set('Processamento terminou; gravação não confirmada. Use Repetir gravação pendente, sem repetir ASR/LLM.')
            else:
                self.load_history()
                self.status.set(f'Execução {result.run_id} registrada ({label(result.status)}). Consulte a nova sessão; LLM não decide alertas.')
        self.dispatch(lambda progress:self.workspace.process(database,patient,case,session_at,progress,
            llm_enabled=True,cloud_text_authorized=True),ready,'Whisper local e análise GPT-OSS cloud opcionais…')
