"""Explicit read-only desktop entry point: python -m medassistmultimodal.desktop."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog
from tkinter.scrolledtext import ScrolledText
from uuid import UUID

from medassistmultimodal.application.desktop_history import HistoryError, HistoryState
from medassistmultimodal.infrastructure.desktop_history import SQLiteHistoryReader

MESSAGES = {
    'database_unavailable': 'Base indisponível. Selecione um arquivo existente dentro do projeto.',
    'invalid_patient': 'Informe um paciente fictício no formato PAT-001.',
    'history_unavailable': 'Não foi possível consultar o histórico. Confira a base e sua versão.',
    'evidence_missing': 'Evidência ausente. Integridade não confirmada.',
    'evidence_invalid': 'Evidência ou metadados inválidos. Integridade não confirmada.',
    'evidence_unsupported': 'Versão da evidência não suportada. Integridade não confirmada.',
    'session_not_found': 'Sessão não encontrada nesta base.',
}
LABELS = {
    'completed': 'Concluído tecnicamente', 'degraded': 'Resultado parcial', 'failed': 'Falhou',
    'pending_review': 'Pendente de revisão', 'reviewed': 'Revisado', 'dismissed': 'Descartado',
    'human_recording': 'Voz humana — relato simulado', 'synthetic_tts': 'Voz sintética (TTS)',
    'disabled': 'Desativada', 'timeout': 'Prazo excedido', 'succeeded': 'Concluída',
    'succeeded_with_mentions': 'Concluída com menções', 'succeeded_no_mentions': 'Sem menções configuradas',
}


def label(value):
    return LABELS.get(value, str(value) if value is not None else 'Não disponível')


def local_time(value):
    try:
        return datetime.fromisoformat(value).astimezone().isoformat(timespec='seconds')
    except (TypeError, ValueError):
        return 'Não disponível'


def audio_text(detail):
    """Pure presentation; no inferred provider identity or clinical judgment."""
    data = detail.document
    if not data['documents']:
        return 'Esta sessão existe, mas não contém eventos de áudio. Outras modalidades podem estar presentes.'
    blocks = []
    for entry in data['documents']:
        doc = entry['evidence']
        lines = [f"Integridade: verificada | Estado: {label(doc['summary']['status'])}",
                 f"Paciente fictício: {doc['identity']['patient_id']} | Execução: {doc['identity']['run_id']}",
                 f"Sessão (local): {local_time(doc['time']['session_timestamp_utc'])}",
                 f"Processamento (local): {local_time(doc['time']['processing_timestamp_utc'])}",
                 f"Origem: {label(doc['input']['origin_kind'])}",
                 f"Mídia: {doc['input']['audio_ref']}",
                 f"Permissão declarada: {doc['input']['permission_declared']}",
                 f"Referência de permissão: {doc['input']['permission_ref']}", '', 'ETAPAS']
        for name in ('asr', 'acoustics', 'rules', 'llm'):
            stage = doc[name]; provider = stage.get('provider') or {}
            mock = provider.get('is_mock', stage.get('is_mock'))
            origin = 'mock' if mock is True else 'real' if mock is False else 'não disponível'
            lines.append(f"{name.upper()}: {label(stage['status'])} | processamento: {origin} | "
                         f"fonte: {provider.get('source', stage.get('processor', stage.get('version', 'Não disponível')))} | "
                         f"modelo: {provider.get('model', 'Não disponível')}")
            if stage.get('error'): lines.append(f"  Motivo registrado: {stage['error']}")
        transcript = doc['asr'].get('result')
        lines += ['', 'TRANSCRIÇÃO ORIGINAL', transcript['text'] if transcript else 'Não disponível — consulte a etapa ASR.',
                  '', 'REGRAS E CONTEXTO']
        for item in doc['rules']['items']:
            lines.append(f"• {item['term']} | {item['context']} | {item['classification']}\n  {item['sentence']}")
        if not doc['rules']['items']:
            lines.append('Nenhuma menção configurada encontrada.' if doc['rules']['status']=='succeeded_no_mentions'
                         else 'Menções não disponíveis — consulte a etapa de regras.')
        lines += ['', 'ANÁLISE LLM (opcional; não decide alertas)',
                  json.dumps(doc['llm'].get('result'), ensure_ascii=False, indent=2)
                  if doc['llm'].get('result') else label(doc['llm']['status']),
                  '', 'DESCRITORES TÉCNICOS (não diagnósticos)',
                  json.dumps(doc['acoustics'].get('result'), ensure_ascii=False, indent=2),
                  f"Unidades: {doc['acoustics'].get('units', 'Não disponível')}",
                  '', f"Evidência: {entry['reference']}", f"SHA-256: {entry['sha256']}",
                  'O estado atual de revisão está na aba Alertas e revisão.']
        blocks.append('\n'.join(lines))
    return '\n\n' + ('\n\n' + '─'*50 + '\n\n').join(blocks)


class DesktopApp:
    def __init__(self, root, *, reader, project_root):
        self.root = root; self.reader = reader; self.project_root = Path(project_root)
        self.state = HistoryState(); self.current_database = None
        root.title('MedAssistMultimodal'); root.geometry('1100x750'); root.minsize(900, 600)
        ttk.Label(root, text='MedAssistMultimodal', font=('Segoe UI', 16, 'bold')).pack(anchor='w', padx=12, pady=(10, 0))
        ttk.Label(root, text='POC acadêmica — apoio à revisão profissional | Consulta somente leitura').pack(anchor='w', padx=12)
        bar = ttk.Frame(root); bar.pack(fill='x', padx=12, pady=8)
        self.database_bar = bar
        self.database = tk.StringVar(); self.patient = tk.StringVar(value='PAT-001')
        ttk.Label(bar, text='Base:').pack(side='left')
        ttk.Entry(bar, textvariable=self.database).pack(side='left', fill='x', expand=True, padx=5)
        ttk.Button(bar, text='Selecionar base…', command=self.choose_database).pack(side='left')
        ttk.Label(bar, text='Paciente fictício:').pack(side='left', padx=(10, 3))
        ttk.Entry(bar, textvariable=self.patient, width=10).pack(side='left')
        ttk.Button(bar, text='Consultar', command=self.load_history).pack(side='left', padx=5)
        self.status = tk.StringVar(value='Selecione uma base existente e consulte o histórico.')
        ttk.Label(root, textvariable=self.status, wraplength=1050).pack(fill='x', padx=12, pady=4)
        panes = ttk.Panedwindow(root, orient='horizontal'); panes.pack(fill='both', expand=True, padx=12, pady=(4,12))
        left = ttk.Frame(panes); panes.add(left, weight=1)
        self.history_pane = left
        ttk.Label(left, text='Histórico de sessões').pack(anchor='w')
        self.sessions = ttk.Treeview(left, columns=('time',), show='tree headings', selectmode='browse', height=12)
        self.sessions.heading('#0', text='Sessão'); self.sessions.heading('time', text='Data local')
        self.sessions.column('#0', width=170); self.sessions.column('time', width=165)
        scroll = ttk.Scrollbar(left, orient='vertical', command=self.sessions.yview)
        self.sessions.configure(yscrollcommand=scroll.set); scroll.pack(side='right', fill='y'); self.sessions.pack(fill='both', expand=True)
        self.sessions.bind('<<TreeviewSelect>>', self.select_session)
        self.tabs = ttk.Notebook(panes); panes.add(self.tabs, weight=3)
        self.audio = self.text_tab('Áudio')
        for name in ('Vídeo', 'Anomalias'):
            widget = self.text_tab(name); self.set_text(widget, 'Integração com a interface pendente.\nCapacidade experimental; sem execução nesta tela.')
        review = ttk.Frame(self.tabs); self.tabs.add(review, text='Alertas e revisão')
        self.audio_tab, self.video_tab, self.anomaly_tab = [root.nametowidget(t) for t in self.tabs.tabs()[:3]]
        self.review_tab = review
        ttk.Label(review, text='Itens de áudio para revisão — consulta; sem severidade clínica automática.', wraplength=650).pack(anchor='w', pady=5)
        event_table = ttk.Frame(review); event_table.pack(fill='x')
        self.events = ttk.Treeview(event_table, columns=('status', 'kind'), show='tree headings', selectmode='browse', height=7)
        self.events.heading('#0', text='Evento'); self.events.heading('status', text='Revisão atual'); self.events.heading('kind', text='Item')
        self.events.column('#0', width=150); self.events.column('status', width=140); self.events.column('kind', width=170)
        event_scroll = ttk.Scrollbar(event_table, orient='vertical', command=self.events.yview)
        self.events.configure(yscrollcommand=event_scroll.set)
        event_scroll.pack(side='right', fill='y'); self.events.pack(fill='x', expand=True)
        self.events.bind('<<TreeviewSelect>>', self.select_event)
        self.event_detail = ScrolledText(review, wrap='word', font=('Segoe UI',10)); self.event_detail.pack(fill='both', expand=True)
        self.clear_details()

    def text_tab(self, name):
        frame = ttk.Frame(self.tabs); self.tabs.add(frame, text=name)
        widget = ScrolledText(frame, wrap='word', font=('Segoe UI',10), padx=10, pady=10)
        widget.pack(fill='both', expand=True); return widget

    @staticmethod
    def set_text(widget, text):
        widget.configure(state='normal'); widget.delete('1.0', 'end'); widget.insert('1.0', text); widget.configure(state='disabled')

    def clear_details(self):
        self.set_text(self.audio, 'Selecione uma sessão.')
        self.set_text(self.event_detail, 'Selecione um evento. Revisão gravável será implementada na tarefa 5.')
        self.events.delete(*self.events.get_children())

    def choose_database(self):
        path = filedialog.askopenfilename(parent=self.root, initialdir=self.project_root/'data/interim',
            title='Selecionar base existente para consulta', filetypes=[('SQLite', '*.sqlite3 *.db *.sqlite'), ('Todos', '*')])
        if path:
            self.database.set(path); self.load_history()

    def load_history(self):
        token = self.state.begin(); self.current_database = None
        self.sessions.delete(*self.sessions.get_children()); self.clear_details()
        self.status.set('Carregando histórico…'); self.root.update_idletasks()
        try:
            rows = self.reader.sessions(self.database.get(), self.patient.get())
            self.state.rows = rows; self.state.status = 'ready' if rows else 'empty'
            self.current_database = self.database.get()
            for row in rows:
                self.sessions.insert('', 'end', iid=row.session_id, text=row.session_id, values=(local_time(row.started_at),))
            self.status.set(f'{len(rows)} sessão(ões) para {self.patient.get()} | Somente leitura.' if rows else 'Nenhuma sessão encontrada para este paciente nesta base.')
        except HistoryError as exc:
            self.state.fail(token, exc.code); self.status.set(MESSAGES.get(exc.code, MESSAGES['history_unavailable']))

    def select_session(self, _event=None):
        selected = self.sessions.selection()
        if not selected or not self.current_database: return
        token = self.state.begin(selected[0]); self.clear_details()
        self.status.set('Carregando evidência…'); self.root.update_idletasks()
        try:
            detail = self.reader.detail(self.current_database, UUID(selected[0]))
            if not self.state.receive_detail(token, detail): return
            data = detail.document; self.set_text(self.audio, audio_text(detail))
            for row in data['events']:
                event = row['event']; item = row['evidence_item']
                self.events.insert('', 'end', iid=event['event_id'], text=event['event_id'],
                    values=(label(event['review_status']), item.get('term', 'Resumo técnico')))
            self.status.set('Evidência verificada | Consulta somente leitura.' if data['documents'] else 'Sessão sem eventos de áudio.')
        except HistoryError as exc:
            self.state.fail(token, exc.code); self.status.set(MESSAGES.get(exc.code, MESSAGES['history_unavailable']))
            self.set_text(self.audio, self.status.get())

    def select_event(self, _event=None):
        selected = self.events.selection()
        if not selected or self.state.detail is None: return
        data = self.state.detail.document
        row = next(r for r in data['events'] if r['event']['event_id']==selected[0])
        text = 'Estado atual (SQLite): ' + label(row['event']['review_status'])
        text += '\nConfiança: ' + str(row['event']['confidence'] if row['event']['confidence'] is not None else 'Não disponível')
        text += '\n\nEVENTO E EVIDÊNCIA\n' + json.dumps(row, ensure_ascii=False, indent=2)
        text += '\n\nHISTÓRICO DE REVISÃO\n' + json.dumps(data['review_histories'][selected[0]], ensure_ascii=False, indent=2)
        text += '\n\nConsulta não altera revisão nem certifica validade clínica.'
        self.set_text(self.event_detail, text)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', help='Base existente dentro do projeto; somente leitura')
    parser.add_argument('--patient', default='PAT-001')
    args = parser.parse_args(argv)
    project = Path(__file__).resolve().parents[2]
    root = tk.Tk(); app = DesktopApp(root, reader=SQLiteHistoryReader(project), project_root=project)
    app.patient.set(args.patient)
    if args.database:
        app.database.set(args.database); root.after(0, app.load_history)
    root.mainloop()


if __name__ == '__main__':
    main()
