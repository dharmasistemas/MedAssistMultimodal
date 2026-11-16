"""Desktop with explicit workspace, one worker and audited review; cloud disabled."""
import os
# Must precede imports of NumPy/audio modules on the supported entry point.
os.environ['MKL_THREADING_LAYER'] = 'SEQUENTIAL'
os.environ['OMP_NUM_THREADS'] = '4'
os.environ['HF_HUB_OFFLINE'] = '1'

import argparse
from datetime import datetime, timezone
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
from uuid import UUID, uuid4

from medassistmultimodal.desktop import DesktopApp, MESSAGES, audio_text, label, local_time
from medassistmultimodal.application.desktop_worker import DesktopWorker
from medassistmultimodal.application.review_event import EventReviewRequest
from medassistmultimodal.domain.events import ReviewStatus
from medassistmultimodal.infrastructure.desktop_history import SQLiteHistoryReader
from medassistmultimodal.infrastructure.desktop_workspace import DesktopWorkspace

ERRORS = dict(MESSAGES, workspace_required='Crie ou selecione uma cópia de trabalho. Bases históricas são somente leitura.',
    operation_failed='A operação não foi concluída. Consulte o histórico antes de tentar novamente.',
    review_conflict='Conflito de revisão. Consulte novamente a sessão e seu histórico; não reabra o evento.',
    corpus_unavailable='Corpus simulado indisponível ou caso inválido.',
    permission_required='A gravação não tem permissão declarada disponível.',
    audio_changed='O arquivo de áudio difere do hash cadastrado.',
    audio_rejected='Entrada rejeitada. Nenhuma sessão foi registrada.',
    model_unavailable='Modelo local ausente ou diferente do manifesto. Nenhum download automático.')
STAGES = dict(validating='Conferindo entrada…', loading_model='Conferindo modelo local…',
              processing='Processando Whisper e regras locais…', saving='Persistindo evidência e eventos…')


class WorkflowApp(DesktopApp):
    def __init__(self, root, *, reader, workspace, project_root, worker=None):
        self.worker = worker or DesktopWorker()
        self.workspace = workspace
        self.on_success = None
        self.on_error = None
        self.closing = False
        self.pending_review = None
        self.pending_process = None
        self.loaded_patient = None
        self._disabled = []
        super().__init__(root, reader=reader, project_root=project_root)
        controls = ttk.Frame(root); controls.pack(fill='x', padx=12, pady=4, before=self.tabs.master)
        self.audio_actions = controls
        ttk.Button(controls, text='Criar cópia de trabalho', command=self.create_workspace).pack(side='left')
        ttk.Label(controls, text='Áudio simulado:').pack(side='left', padx=(12,4))
        self.case = tk.StringVar(value='A08')
        # Listing is an explicit local metadata read, never ASR or cloud.
        try: cases = workspace.clips()
        except Exception: cases = ()
        ttk.Combobox(controls, textvariable=self.case, values=cases, width=6, state='readonly').pack(side='left')
        ttk.Label(controls, text='Horário da sessão (com fuso):').pack(side='left', padx=4)
        self.session_at = tk.StringVar(value=datetime.now(timezone.utc).isoformat(timespec='seconds'))
        ttk.Entry(controls, textvariable=self.session_at, width=27).pack(side='left')
        ttk.Button(controls, text='Processar localmente', command=self.process_audio).pack(side='left', padx=4)
        ttk.Button(controls, text='Repetir gravação pendente', command=self.retry_process).pack(side='left')
        self.context = tk.StringVar(value='Consulta histórica | Whisper local | LLM desativada | Sem envio cloud')
        ttk.Label(root, textvariable=self.context).pack(fill='x', padx=12, before=self.tabs.master)
        review = self.event_detail.frame.master
        form = ttk.Frame(review); form.pack(fill='x', pady=4, before=self.event_detail.frame)
        self.reviewer = tk.StringVar(); self.reason = tk.StringVar()
        ttk.Label(form, text='Revisor (ID opaco):').grid(row=0, column=0, sticky='w')
        ttk.Entry(form, textvariable=self.reviewer, width=20).grid(row=0, column=1, sticky='ew')
        ttk.Label(form, text='Motivo:').grid(row=1, column=0, sticky='w')
        ttk.Entry(form, textvariable=self.reason).grid(row=1, column=1, columnspan=3, sticky='ew')
        form.columnconfigure(1, weight=1)
        ttk.Button(form, text='Registrar como revisado', command=lambda:self.submit_review(ReviewStatus.REVIEWED)).grid(row=2,column=0,pady=4)
        ttk.Button(form, text='Descartar item', command=lambda:self.submit_review(ReviewStatus.DISMISSED)).grid(row=2,column=1,pady=4,sticky='w')
        ttk.Button(form, text='Reenviar mesma revisão', command=self.retry_review).grid(row=2,column=2,pady=4)
        root.protocol('WM_DELETE_WINDOW', self.request_close)
        self.poll_id = root.after(75, self.poll)

    def _set_busy(self, busy):
        if busy:
            self._disabled = []
            def visit(widget):
                for child in widget.winfo_children():
                    if isinstance(child, (ttk.Button, ttk.Entry, ttk.Combobox)):
                        self._disabled.append((child, str(child.cget('state')))); child.configure(state='disabled')
                    visit(child)
            visit(self.root)
        else:
            for child, state in self._disabled:
                if child.winfo_exists(): child.configure(state=state)
            self._disabled = []

    def dispatch(self, operation, success, message, failure=None):
        if self.worker.busy or self.closing: return False
        self.on_success = success; self.on_error = failure; self._set_busy(True); self.status.set(message)
        self.worker.start(operation)
        return True

    def poll(self):
        for message in self.worker.drain():
            if message.kind=='progress':
                self.status.set(STAGES.get(message.value, 'Operação em andamento…'))
                continue
            callback = self.on_success; failure = self.on_error
            self.on_success = None; self.on_error = None; self._set_busy(False)
            if message.kind=='error':
                if failure is not None: failure(message.value)
                self.status.set(ERRORS.get(message.value, ERRORS['operation_failed']))
                # Reload explicitly after conflicts; no automatic new review.
            elif callback is not None and not self.closing:
                callback(message.value)
        if self.closing and not self.worker.busy:
            self.root.destroy(); return
        self.poll_id = self.root.after(75, self.poll)

    def request_close(self):
        if not self.worker.busy:
            self.root.after_cancel(self.poll_id); self.root.destroy(); return
        if messagebox.askyesno('Operação em andamento',
            'Fechar quando a operação terminar? Ela continuará até concluir; não será cancelada.', parent=self.root):
            self.closing = True
            self.status.set('Aguardando a operação terminar para fechar. Nenhum cancelamento foi enviado.')

    def load_history(self):
        if self.worker.busy or self.closing: return
        database = self.database.get(); patient = self.patient.get()
        token = self.state.begin(); self.current_database = None; self.loaded_patient = None
        self.sessions.delete(*self.sessions.get_children()); self.clear_details()
        def show(rows):
            if token!=self.state.generation: return
            self.state.rows = rows; self.state.status = 'ready' if rows else 'empty'
            self.current_database = database; self.loaded_patient = patient
            for row in rows:
                self.sessions.insert('', 'end', iid=row.session_id, text=row.session_id, values=(local_time(row.started_at),))
            mode = 'Cópia de trabalho' if self.workspace.is_workspace(database) else 'Consulta histórica — somente leitura'
            self.context.set(mode + ' | Whisper local | LLM desativada | Sem envio cloud')
            self.status.set(f'{len(rows)} sessão(ões) para {patient} | {mode}' if rows else 'Nenhuma sessão encontrada para este paciente nesta base.')
        self.dispatch(lambda progress:self.reader.sessions(database,patient), show, 'Carregando histórico…',
                      lambda code:self.state.fail(token,code))

    def select_session(self, _event=None):
        if self.worker.busy or self.closing: return
        selected = self.sessions.selection()
        if not selected or not self.current_database: return
        database = self.current_database; session = UUID(selected[0]); token = self.state.begin(str(session))
        self.clear_details()
        def show(detail):
            if not self.state.receive_detail(token, detail): return
            data = detail.document; self.set_text(self.audio, audio_text(detail))
            for row in data['events']:
                event = row['event'];item = row['evidence_item']
                self.events.insert('', 'end', iid=event['event_id'], text=event['event_id'],
                    values=(label(event['review_status']), item.get('term','Resumo técnico')))
            self.status.set('Evidência verificada. Selecione um evento para consultar ou revisar.' if data['documents'] else 'Sessão sem eventos de áudio.')
        self.dispatch(lambda progress:self.reader.detail(database,session), show, 'Carregando evidência…',
                      lambda code:self.state.fail(token,code))

    def select_event(self, _event=None):
        if self.worker.busy or self.closing: return
        super().select_event(_event)

    def create_workspace(self):
        if self.worker.busy: return
        source = self.current_database; patient = self.loaded_patient
        if not source:
            self.status.set('Consulte uma base válida antes de criar a cópia de trabalho.'); return
        if self.database.get()!=source or self.patient.get()!=patient:
            self.status.set('Os campos foram alterados. Clique em Consultar antes de criar a cópia.'); return
        if not messagebox.askyesno('Criar cópia de trabalho',
            'Criar uma nova cópia do banco selecionado para processamento e revisão? A base de origem será preservada.', parent=self.root): return
        def ready(database):
            self.database.set(database); self.patient.set(patient); self.load_history()
        self.dispatch(lambda progress:self.workspace.create_copy(source,patient), ready, 'Criando cópia de trabalho…')

    def _require_workspace(self):
        if not self.current_database or not self.workspace.is_workspace(self.current_database):
            self.status.set(ERRORS['workspace_required']); return False
        if self.database.get()!=self.current_database or self.patient.get()!=self.loaded_patient:
            self.status.set('Os campos foram alterados. Clique em Consultar antes de executar a operação.'); return False
        return True

    def process_audio(self):
        if self.worker.busy or not self._require_workspace(): return
        database = self.current_database;patient = self.loaded_patient;case = self.case.get()
        try:
            session_at = datetime.fromisoformat(self.session_at.get())
            if session_at.tzinfo is None or session_at.utcoffset() is None: raise ValueError()
        except ValueError:
            self.status.set('Informe data/hora ISO 8601 com fuso, por exemplo 2026-11-07T12:00:00-03:00.'); return
        if not messagebox.askyesno('Processar áudio simulado',
            f'Processar {case} para {patient} com Whisper local e regras?\nHorário da sessão: {session_at.isoformat()}\nLLM desativada. Nenhum envio cloud.',parent=self.root): return
        self.pending_process = None
        def ready(result):
            if not result.persisted:
                self.pending_process = (database,result.run_id)
                self.status.set('Processamento terminou, mas a gravação não foi confirmada. Use Repetir gravação pendente; não execute o áudio de novo.')
            else:
                self.load_history()
                self.status.set(f'Execução {result.run_id} registrada ({label(result.status)}). Consulte a nova sessão no histórico.')
        self.dispatch(lambda progress:self.workspace.process(database,patient,case,session_at,progress),ready,'Preparando áudio local…')

    def retry_process(self):
        if self.worker.busy or not self._require_workspace(): return
        if not self.pending_process or self.pending_process[0]!=self.current_database:
            self.status.set('Nenhuma gravação pendente nesta base durante esta sessão do aplicativo.'); return
        database,run_id = self.pending_process
        def ready(result):
            self.pending_process = None;self.load_history()
            self.status.set(f'Gravação confirmada para {result.run_id}; nenhuma nova inferência foi feita.')
        self.dispatch(lambda progress:self.workspace.retry_persistence(database,run_id),ready,'Repetindo somente a persistência…')

    def submit_review(self, target):
        if self.worker.busy or not self._require_workspace(): return
        selected = self.events.selection()
        if not selected or not self.state.detail:
            self.status.set('Selecione um evento com evidência verificada.');return
        data = self.state.detail.document
        if data['integrity']!='verified': return
        row = next(r for r in data['events'] if r['event']['event_id']==selected[0]);event=row['event']
        if event['review_status']!='pending_review':
            self.status.set('Evento já revisado ou descartado. Não há reabertura automática.');return
        try:
            request=EventReviewRequest(review_id=uuid4(),event_id=UUID(selected[0]),reviewer_ref=self.reviewer.get(),
                reviewed_at=datetime.now(timezone.utc),reason=self.reason.get(),target_status=target,scope='human_review')
        except ValueError:
            self.status.set('Informe ID opaco de revisor (até 64 caracteres) e motivo em uma linha (até 500 caracteres).');return
        if not messagebox.askyesno('Confirmar revisão explícita',
            f'Evento: {selected[0]}\nDecisão: {label(target.value)}\nRevisor declarado: {request.reviewer_ref}\nMotivo: {request.reason}\n\nEsta operação não certifica validade clínica.',parent=self.root):return
        self.pending_review=(self.current_database,UUID(data['session']['session_id']),request,event['evidence_ref'])
        self.retry_review()

    def retry_review(self):
        if self.worker.busy or not self._require_workspace():return
        if not self.pending_review or self.pending_review[0]!=self.current_database:
            self.status.set('Nenhuma solicitação de revisão para reenviar nesta base.');return
        database,session,request,reference=self.pending_review
        def ready(audit_id):
            # Read again instead of changing a widget status optimistically.
            self.select_session()
            self.status.set(f'Revisão confirmada. Auditoria {audit_id}. Recarregando estado e histórico.')
        self.dispatch(lambda progress:self.workspace.review(database,session,request,reference),ready,'Registrando revisão e auditoria…')


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database');parser.add_argument('--patient',default='PAT-001')
    args=parser.parse_args(argv);project=Path(__file__).resolve().parents[2]
    root=tk.Tk();app=WorkflowApp(root,reader=SQLiteHistoryReader(project),workspace=DesktopWorkspace(project),project_root=project)
    app.patient.set(args.patient)
    if args.database:app.database.set(args.database);root.after(0,app.load_history)
    root.mainloop()


if __name__=='__main__':main()
