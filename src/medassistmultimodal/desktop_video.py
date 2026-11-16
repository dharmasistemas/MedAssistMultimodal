"""RGB video tab: dataset history stays separate from the fictional patient."""
from pathlib import Path
from io import BytesIO
from PIL import Image,ImageTk
import tkinter as tk
from tkinter import ttk,messagebox
from tkinter.scrolledtext import ScrolledText
from uuid import UUID,uuid4

from medassistmultimodal.desktop_multimodal import MultimodalApp,ERRORS
from medassistmultimodal.desktop import label,local_time
from medassistmultimodal.infrastructure.desktop_video import VideoWorkspace,VideoHistoryReader,ELBOW_CASES,validate_interval
from medassistmultimodal.providers.whisper_local import checked_path
from medassistmultimodal.application.desktop_history import HistoryError

ERRORS.update(video_assets_invalid='Vídeo/modelo local ausente ou diferente do manifesto. Nenhum download automático.',
    video_interval_invalid='Use um trecho conhecido com seus frames exatos ou o modo manual entre 0 e 449.')


def elbow_text(d):
    e=d.get('elbow_analysis')
    if e is None:return 'Flexão do cotovelo: não avaliada nesta execução histórica/manual.'
    labels={'deviation':'Sinal experimental de flexão do cotovelo — requer revisão',
        'no_deviation':'Sem sinal desse desvio — não comprova exercício correto',
        'not_analyzable':'Evidência insuficiente para avaliar flexão do cotovelo'}
    fraction='Indisponível' if e['bent_fraction'] is None else f"{e['bent_fraction']:.1%}"
    return '\n'.join([labels[e['status']],
        f"Regra: ângulo <150° em pelo menos 20% das medidas válidas; cobertura mínima 80%.",
        f"Cobertura original da regra: {e['coverage']:.1%} | Fração: {fraction} | Frame de evidência: {e['evidence_frame']}",
        'Intervalo fornecido; regra usa ângulos originais. A tabela abaixo usa a máscara temporal para ciclos, que pode ter cobertura diferente.'])


def video_text(detail):
    record=detail.document['videos'][0];d=record['evidence'];s=d['source'];r=d['summary']
    return '\n'.join([elbow_text(d),'Integridade: verificada | RGB experimental | Sem validação clínica',
        f"Dataset: {s['dataset_id']} | Participante: {s['participant_ref']}",
        'Identidade independente de PAT-001 e dos locutores dos áudios.',
        f"Processamento local: {local_time(d['processed_at'])} | Horário de captura desconhecido",
        f"Frames inclusivos: {s['first_frame']}–{s['last_frame']} | {s['fps']} FPS | Tempo relativo: {s['first_frame']/s['fps']:.3f}–{s['last_frame']/s['fps']:.3f} s",
        f"Fonte: {s['video_ref']} | Mock: {s['is_mock']}",
        'Pose: MediaPipe Tasks world 3D; ângulos em graus. A imagem do frame é RGB original, sem sobreposição de landmarks.',
        f"Frames processados: {r['input_frames']} | Ciclos candidatos detectados: {r['detected_cycles']}",
        'Contagem detectada não é o total real de repetições; zero não comprova ausência de movimento.',
        f"Cobertura utilizável cotovelo: {r['coverage']['right_elbow']:.2%}",
        f"Cobertura utilizável braço–tronco: {r['coverage']['right_arm_trunk']:.2%}",
        f"Intervalos de qualidade técnica: {r['quality_intervals']}",
        'Falhas de visibilidade/descontinuidade são limitações técnicas, não erros clínicos do exercício.',
        'Sem inferência de diagnóstico, dor ou relação com áudio/vitais/prescrições.',
        'A segmentação do dia 10 foi avaliada em NPY; essas métricas não validam esta nova execução RGB.',
        'Alinhamento RGB/NPY completo não validado; não interpretar tempos como sincronizados com outras modalidades.',
        f"Evidência: {record['reference']}",f"SHA-256: {record['sha256']}",
        'Selecione os itens em Alertas e revisão para consultar a evidência e registrar conferência individual.'])


def fit_preview_image(image,width,height):
    """Resample from the preserved RGB source; never decimate then enlarge pixels."""
    scale=min(max(1,width)/image.width,max(1,height)/image.height,1.0)
    size=(max(1,int(image.width*scale)),max(1,int(image.height*scale)))
    return image.resize(size,resample=Image.Resampling.LANCZOS)


class VideoApp(MultimodalApp):
    def __init__(self,root,**kwargs):
        self.video_active=False;self.pending_video=None;self.video_ids=[];self.preview_image=None;self.preview_original=None
        self.preview_generation=0;self.preview_after=None
        super().__init__(root,**kwargs)
        if getattr(self, 'simplified_video', False):
            from medassistmultimodal.desktop_video_layout import build_video_tab
            build_video_tab(self)
        else:
            self._build_classic_video()
        self.clear_details()
        review=root.nametowidget(self.tabs.tabs()[3])
        for child in review.winfo_children():
            if isinstance(child,ttk.Label) and str(child.cget('text')).startswith('Itens de áudio'):
                child.configure(text='Eventos da sessão selecionada — evidência e revisão individual, sem severidade clínica automática.')

    def _build_classic_video(self):
        root=self.root
        frame=root.nametowidget(self.tabs.tabs()[1])
        for child in frame.winfo_children():child.destroy()
        frame.columnconfigure(0,weight=1)
        frame.rowconfigure(3,weight=1,minsize=180)
        ttk.Label(frame,text='REHAB26 — participante de dataset independente do paciente fictício',wraplength=650).grid(row=0,column=0,sticky='w',padx=6,pady=4)
        controls=ttk.Frame(frame);controls.grid(row=1,column=0,sticky='ew',padx=6)
        self.video_case=tk.StringVar(value='Manual (ciclos)')
        self.video_case_choices=ttk.Combobox(controls,textvariable=self.video_case,state='readonly',width=18,
            values=('Manual (ciclos)',*ELBOW_CASES))
        self.video_case_choices.pack(side='left',padx=3)
        self.video_case_choices.bind('<<ComboboxSelected>>',self.choose_video_case)
        self.video_first=tk.StringVar(value='20');self.video_last=tk.StringVar(value='99')
        ttk.Label(controls,text='Frames:').pack(side='left')
        ttk.Entry(controls,textvariable=self.video_first,width=5).pack(side='left')
        ttk.Label(controls,text='até').pack(side='left');ttk.Entry(controls,textvariable=self.video_last,width=5).pack(side='left')
        ttk.Button(controls,text='Analisar RGB local',command=self.process_video).pack(side='left',padx=4)
        ttk.Button(controls,text='Repetir gravação pendente',command=self.retry_video).pack(side='left')
        history=ttk.Frame(frame);history.grid(row=2,column=0,sticky='ew',padx=6,pady=4)
        ttk.Button(history,text='Consultar vídeos nesta base',command=self.load_video_history).pack(side='left')
        self.video_session=tk.StringVar();self.video_choices=ttk.Combobox(history,textvariable=self.video_session,state='readonly',width=30)
        self.video_choices.pack(side='left',fill='x',expand=True,padx=4)
        self.video_choices.bind('<<ComboboxSelected>>',self.select_video)
        ttk.Button(history,text='Exportar sessão',command=self.export_video).pack(side='left')
        body=ttk.Panedwindow(frame,orient='horizontal');body.grid(row=3,column=0,sticky='nsew')
        left=ttk.Frame(body);right=ttk.Frame(body);body.add(left,weight=2);body.add(right,weight=3)
        left.columnconfigure(0,weight=1);left.rowconfigure(0,weight=1)
        self.preview_area=ttk.Frame(left,width=300,height=420)
        self.preview_area.grid(row=0,column=0,sticky='nsew',padx=4,pady=4)
        self.preview_area.grid_propagate(False)
        self.preview_label=ttk.Label(self.preview_area,text='Selecione uma linha da tabela para visualizar o frame RGB.',wraplength=260)
        self.preview_label.place(relx=.5,rely=.5,anchor='center')
        self.preview_area.bind('<Configure>',self.fit_preview)
        self.preview_caption=tk.StringVar(value='Imagem RGB original — sem sobreposição de landmarks.')
        ttk.Label(left,textvariable=self.preview_caption,wraplength=300).grid(row=1,column=0,sticky='ew',padx=4,pady=4)
        right.columnconfigure(0,weight=1)
        right.rowconfigure(0,weight=3,minsize=70);right.rowconfigure(1,weight=2,minsize=100)
        self.video_summary=ScrolledText(right,wrap='word',font=('Segoe UI',10),height=10)
        self.video_summary.grid(row=0,column=0,sticky='nsew')
        table=ttk.Frame(right);table.grid(row=1,column=0,sticky='nsew')
        table.columnconfigure(0,weight=1);table.rowconfigure(0,weight=1)
        self.video_samples=ttk.Treeview(table,columns=('frame','time','elbow','arm','quality'),show='headings',height=5,selectmode='browse')
        for c,t in [('frame','Frame'),('time','Tempo relativo (s)'),('elbow','Cotovelo (°)'),('arm','Braço–tronco (°)'),('quality','Qualidade técnica')]:
            self.video_samples.heading(c,text=t);self.video_samples.column(c,width=100)
        self.video_scroll=ttk.Scrollbar(table,orient='vertical',command=self.video_samples.yview)
        self.video_scroll.grid(row=0,column=1,sticky='ns')
        horizontal=ttk.Scrollbar(table,orient='horizontal',command=self.video_samples.xview)
        horizontal.grid(row=1,column=0,sticky='ew')
        self.video_samples.configure(yscrollcommand=self.video_scroll.set,xscrollcommand=horizontal.set)
        self.video_samples.grid(row=0,column=0,sticky='nsew')
        self.video_samples.bind('<<TreeviewSelect>>',self.select_frame)

    def clear_details(self):
        self.preview_generation+=1
        if self.preview_after is not None:
            self.root.after_cancel(self.preview_after);self.preview_after=None
        self.video_active=False
        super().clear_details()
        if hasattr(self,'video_result'):
            self.video_result.set('Selecione um resultado já processado ou analise um trecho. Sem resultado verificado selecionado.')
        if hasattr(self,'video_summary'):
            self.set_text(self.video_summary,'Selecione um trecho D9 para avaliar cotovelo, ou modo manual (frames 0–449) para ciclos. Consulte também sessões já processadas.')
            self.video_samples.delete(*self.video_samples.get_children())
            self.preview_label.configure(image='',text='Selecione uma linha da tabela para visualizar o frame RGB.');self.preview_image=None;self.preview_original=None
            self.preview_caption.set('Imagem RGB original — sem sobreposição de landmarks.')

    def load_history(self):
        if hasattr(self,'video_choices') and not self.worker.busy:
            self.video_ids=[];self.video_choices.configure(values=());self.video_session.set('')
        super().load_history()

    def load_video_history(self):
        if self.worker.busy:return
        if not self.current_database or self.database.get()!=self.current_database:
            self.status.set('Consulte primeiro a base selecionada.');return
        database=self.current_database;self.clear_details();self.video_ids=[];self.video_session.set('');self.video_choices.configure(values=())
        def show(rows):
            self.video_ids=[str(s.session_id) for s in rows]
            self.video_choices.configure(values=self.video_ids)
            self.status.set(f'{len(rows)} sessão(ões) de vídeo do dataset. Nenhum vínculo com o paciente fictício.')
        self.dispatch(lambda progress:self.reader.dataset_sessions(database),show,'Consultando sessões do dataset…')

    def select_video(self,_event=None):
        if self.worker.busy:return
        sid=self.video_session.get()
        if sid not in self.video_ids or self.database.get()!=self.current_database:
            self.clear_details();return
        database=self.current_database;token=self.state.begin(sid);self.clear_details()
        def show(detail):
            if not self.state.receive_detail(token,detail):return
            self.video_active=True;self.set_text(self.video_summary,video_text(detail))
            if hasattr(self,'video_result'):
                from medassistmultimodal.desktop_video_layout import video_result_text
                self.video_result.set(video_result_text(detail))
            d=detail.document;doc=d['videos'][0]['evidence']
            for f in doc['timeline']:
                values=[f['frame'],f"{f['seconds']:.3f}"]
                for name in ('right_elbow','right_arm_trunk'):
                    degrees=f[name]['degrees']
                    values.append(f'{degrees:.1f}' if degrees is not None and hasattr(self,'video_result') else degrees if degrees is not None else 'Indisponível')
                values.append(f"{f['right_elbow']['state']} / {f['right_arm_trunk']['state']}")
                self.video_samples.insert('','end',iid=f"frame-{f['frame']}",values=values)
            for row in d['events']:
                e=row['event'];kind='Desvio experimental: cotovelo' if '&item=/deviation_candidates/' in e['evidence_ref'] else 'Ciclo candidato' if '&item=/cycles/' in e['evidence_ref'] else 'Qualidade técnica' if '&item=/quality_intervals/' in e['evidence_ref'] else 'Resumo experimental'
                self.events.insert('','end',iid=e['event_id'],text='Vídeo '+e['event_id'],values=(label(e['review_status']),kind))
            self.tabs.select(self.video_tab);self.status.set('Vídeo verificado. Identidade de dataset separada; eventos disponíveis em Revisão e relatório.')
        self.dispatch(lambda progress:self.reader.detail(database,UUID(sid)),show,'Conferindo evidência RGB…',lambda code:self.state.fail(token,code))

    def choose_video_case(self,_event=None):
        interval=ELBOW_CASES.get(self.video_case.get(),(20,99))
        self.video_first.set(str(interval[0]));self.video_last.set(str(interval[1]))
        if self.video_case.get()=='Manual (ciclos)' and hasattr(self,'toggle_video_manual') and not self.video_manual_open:
            self.toggle_video_manual()

    def process_video(self):
        if self.worker.busy or not self._require_workspace():return
        if self.pending_video:
            self.status.set('Há gravação de vídeo pendente; use a retentativa antes de outra execução.');return
        try:
            first=int(self.video_first.get());last=int(self.video_last.get())
            case_id=None if self.video_case.get()=='Manual (ciclos)' else self.video_case.get()
            validate_interval(first,last,case_id)
        except (ValueError,HistoryError):
            self.status.set(ERRORS['video_interval_invalid']);return
        if not messagebox.askyesno('Analisar trecho RGB',f'Processar frames {first}–{last} com OpenCV/MediaPipe local?\n'
            'A sessão será do participante REHAB26, independente de PAT-001. Resultado experimental, sem diagnóstico.',parent=self.root):return
        database=self.current_database
        def ready(result):
            if not result.persisted:
                self.pending_video=(database,result.run_id);self.status.set('Extração concluída; gravação não confirmada. Use Repetir gravação pendente.');return
            self.load_video_history();self.status.set(f'Sessão RGB registrada: {result.session_id}. Selecione-a no histórico de vídeo.')
        self.dispatch(lambda progress:self.workspace.process_video(database,first,last,progress,**({'case_id':case_id} if case_id else {})),ready,'Conferindo recursos e processando RGB local…')

    def retry_video(self):
        if self.worker.busy or not self._require_workspace():return
        if not self.pending_video or self.pending_video[0]!=self.current_database:
            self.status.set('Nenhuma gravação de vídeo pendente nesta base.');return
        database,run=self.pending_video
        def ready(result):
            self.pending_video=None;self.load_video_history()
        self.dispatch(lambda progress:self.workspace.retry_video(database,run),ready,'Repetindo somente a persistência do vídeo…')

    def select_frame(self,_event=None):
        selected=self.video_samples.selection()
        if not selected or not self.video_active or not self.state.detail:return
        if self.database.get()!=self.current_database:return
        self.preview_generation+=1;token=self.preview_generation
        if self.preview_after is not None:
            self.root.after_cancel(self.preview_after);self.preview_after=None
        index=int(self.video_samples.item(selected[0],'values')[0])
        session=self.state.detail.document['session']['session_id']
        self.preview_original=None;self.preview_image=None
        self.preview_label.configure(image='',text='Carregando frame selecionado…')
        self.preview_caption.set(f'Frame {index} | Tempo relativo: {index/30:.3f} s | RGB original')
        def current():
            return (token==self.preview_generation and self.video_active and not self.closing
                and self.database.get()==self.current_database and self.state.detail is not None
                and self.state.detail.document['session']['session_id']==session)
        def start():
            self.preview_after=None
            if not current():return
            if self.worker.busy:
                self.preview_after=self.root.after(75,start);return
            def show(ppm):
                if not current():return
                with Image.open(BytesIO(ppm)) as original:
                    self.preview_original=original.convert('RGB')
                self.fit_preview()
                self.status.set(f'Frame RGB original {index}, tempo relativo {index/30:.3f} s. Não é imagem de PAT-001.')
            def fail(code):
                if current():self.preview_label.configure(image='',text='Frame indisponível; confira recursos locais.')
            self.dispatch(lambda progress:self.workspace.preview(index),show,'Decodificando frame selecionado…',fail)
        start()

    def fit_preview(self,_event=None):
        if self.preview_original is None:return
        width=max(1,self.preview_area.winfo_width()-4);height=max(1,self.preview_area.winfo_height()-4)
        resized=fit_preview_image(self.preview_original,width,height)
        self.preview_image=ImageTk.PhotoImage(resized,master=self.root)
        self.preview_label.configure(image=self.preview_image,text='')

    def retry_review(self):
        if not self.video_active:return super().retry_review()
        if self.worker.busy or not self._require_workspace():return
        if not self.pending_review or self.pending_review[0]!=self.current_database:return
        database,session,request,reference=self.pending_review
        def ready(audit):
            self.video_session.set(str(session));self.select_video()
        self.dispatch(lambda progress:self.workspace.review(database,session,request,reference),ready,'Registrando revisão individual do vídeo…')

    def export_video(self):
        if self.worker.busy or not self.video_active or not self._require_workspace():return
        database=self.current_database;sid=UUID(self.state.detail.document['session']['session_id'])
        def operation(progress):
            detail=self.reader.detail(database,sid)
            base=self.workspace.writable_path(database).parent
            path=checked_path(str(base/f'video_export_{uuid4()}.json'),self.project_root)
            with path.open('xb') as stream:stream.write(detail.payload)
            return path.relative_to(self.project_root).as_posix()
        self.dispatch(operation,lambda ref:self.status.set('Exportação técnica da sessão: '+ref),'Exportando sessão de vídeo verificada…')
