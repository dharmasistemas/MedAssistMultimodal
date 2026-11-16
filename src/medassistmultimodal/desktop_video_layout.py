"""Compact video presentation; existing VideoApp owns all processing and evidence."""
import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from medassistmultimodal.infrastructure.desktop_video import ELBOW_CASES


def video_result_text(detail):
    doc = detail.document['videos'][0]['evidence']
    source = doc['source']
    result = doc.get('elbow_analysis')
    labels = {
        'deviation': 'Sinal experimental de flexão de cotovelo — requer revisão.',
        'no_deviation': 'Sem sinal de flexão de cotovelo; não comprova exercício correto.',
        'not_analyzable': 'Dados insuficientes para avaliar flexão de cotovelo.',
    }
    text = labels[result['status']] if result else 'Flexão de cotovelo não avaliada nesta execução manual/histórica.'
    return '\n'.join([
        text,
        f"Frames {source['first_frame']}–{source['last_frame']} · integridade verificada",
        'Resultado experimental, sem validação clínica. Não avalia todos os erros do exercício.',
        'Participante REHAB26; independente do paciente fictício e dos locutores.',
    ])


def build_video_tab(app):
    frame = app.video_tab
    for child in frame.winfo_children():
        child.destroy()
    frame.columnconfigure(1, weight=1)
    frame.rowconfigure(0, weight=1)
    input_host = ttk.Frame(frame)
    input_host.grid(row=0, column=0, sticky='nsw')
    input_host.rowconfigure(0, weight=1)
    input_canvas = tk.Canvas(input_host, width=230, height=1, highlightthickness=0)
    input_canvas.grid(row=0, column=0, sticky='ns')
    input_scroll = ttk.Scrollbar(input_host, orient='vertical', command=input_canvas.yview)
    input_scroll.grid(row=0, column=1, sticky='ns')
    input_canvas.configure(yscrollcommand=input_scroll.set)
    inputs = ttk.Frame(input_canvas, padding=10)
    window = input_canvas.create_window(0, 0, anchor='nw', window=inputs, width=230)
    inputs.bind('<Configure>', lambda event: input_canvas.configure(scrollregion=input_canvas.bbox('all')))
    input_canvas.bind('<Configure>', lambda event: input_canvas.itemconfigure(window, width=event.width))
    app.video_inputs = inputs
    ttk.Label(inputs, text='Entrada', font=('Segoe UI', 11, 'bold')).pack(anchor='w')
    ttk.Label(inputs, text='REHAB26 · Ex1 · câmera 1\nOpenCV + MediaPipe\nParticipante de dataset independente.',
              wraplength=205).pack(anchor='w', pady=(5, 12))
    ttk.Label(inputs, text='Trecho de demonstração').pack(anchor='w')
    app.video_case = tk.StringVar(value='D9-04')
    app.video_case_choices = ttk.Combobox(inputs, textvariable=app.video_case,
        values=(*ELBOW_CASES, 'Manual (ciclos)'), state='readonly', width=22)
    app.video_case_choices.pack(fill='x', pady=5)
    app.video_case_choices.bind('<<ComboboxSelected>>', app.choose_video_case)
    app.video_first = tk.StringVar()
    app.video_last = tk.StringVar()
    app.video_manual_open = False
    app.video_manual = ttk.Frame(inputs)
    app.video_manual.columnconfigure((0, 1), weight=1)
    for column, (title, variable) in enumerate((('Frame inicial', app.video_first), ('Frame final', app.video_last))):
        ttk.Label(app.video_manual, text=title).grid(row=0, column=column, sticky='w', padx=3)
        ttk.Entry(app.video_manual, textvariable=variable, width=9).grid(row=1, column=column, sticky='ew', padx=3)

    def toggle_manual():
        app.video_manual_open = not app.video_manual_open
        app.video_manual_toggle.configure(text='Outras opções de entrada '+('▾' if app.video_manual_open else '▸'))
        if app.video_manual_open:
            app.video_manual.pack(fill='x', pady=5, before=app.video_process_button)
        else:
            app.video_manual.pack_forget()

    app.toggle_video_manual = toggle_manual
    app.video_manual_toggle = ttk.Button(inputs, text='Outras opções de entrada ▸', command=toggle_manual)
    app.video_manual_toggle.pack(fill='x', pady=4)
    app.video_process_button = ttk.Button(inputs, text='Analisar vídeo', command=app.process_video)
    app.video_process_button.pack(fill='x', pady=6)
    ttk.Button(inputs, text='Repetir gravação pendente', command=app.retry_video).pack(fill='x', pady=3)
    ttk.Separator(inputs).pack(fill='x', pady=12)
    ttk.Label(inputs, text='Resultados já processados').pack(anchor='w')
    ttk.Button(inputs, text='Consultar vídeos nesta base', command=app.load_video_history).pack(fill='x', pady=5)
    app.video_session = tk.StringVar()
    app.video_choices = ttk.Combobox(inputs, textvariable=app.video_session, state='readonly', width=22)
    app.video_choices.pack(fill='x', pady=3)
    app.video_choices.bind('<<ComboboxSelected>>', app.select_video)
    ttk.Button(inputs, text='Revisar resultado', command=app.open_review).pack(fill='x', pady=7)

    result = ttk.Frame(frame, padding=10)
    result.grid(row=0, column=1, sticky='nsew')
    result.columnconfigure(0, weight=1)
    result.rowconfigure(2, weight=1)
    ttk.Label(result, text='Resultado do trecho', font=('Segoe UI', 11, 'bold')).grid(row=0, column=0, sticky='w')
    app.video_result = tk.StringVar(value='Selecione um resultado já processado ou analise um trecho.')
    result_label = ttk.Label(result, textvariable=app.video_result, wraplength=650, justify='left')
    result_label.grid(row=1, column=0, sticky='ew', pady=(5, 10))
    body = ttk.Frame(result)
    body.grid(row=2, column=0, sticky='nsew')
    body.columnconfigure(1, weight=1)
    body.rowconfigure(0, weight=1)
    app.video_result_body = body
    portrait = ttk.Frame(body)
    portrait.grid(row=0, column=0, sticky='nw', padx=(0, 12))
    app.preview_area = ttk.Frame(portrait, width=190, height=338)
    app.preview_area.grid(row=0, column=0, sticky='n')
    app.preview_area.grid_propagate(False)
    app.preview_label = ttk.Label(app.preview_area, text='Selecione uma linha\nda tabela para ver o frame.', wraplength=180, justify='center')
    app.preview_label.place(relx=.5, rely=.5, anchor='center')
    app.preview_area.bind('<Configure>', app.fit_preview)
    app.preview_caption = tk.StringVar(value='RGB original · sem sobreposição de landmarks')
    caption = ttk.Label(portrait, textvariable=app.preview_caption, wraplength=190)
    caption.grid(row=1, column=0, sticky='ew', pady=5)
    table = ttk.Frame(body)
    table.grid(row=0, column=1, sticky='nsew')
    table.columnconfigure(0, weight=1)
    table.rowconfigure(1, weight=1)
    ttk.Label(table, text='Frames — selecione uma linha').grid(row=0, column=0, sticky='w', pady=(0, 5))
    app.video_samples = ttk.Treeview(table, columns=('frame', 'time', 'elbow', 'arm', 'quality'),
                                    show='headings', height=8, selectmode='browse')
    for col, title, width in (('frame','Frame',60), ('time','Tempo (s)',80), ('elbow','Cotovelo (°)',95),
                              ('arm','Braço–tronco (°)',115), ('quality','Qualidade técnica',175)):
        app.video_samples.heading(col, text=title)
        app.video_samples.column(col, width=width, minwidth=width, stretch=False)
    app.video_samples.grid(row=1, column=0, sticky='nsew')
    app.video_scroll = ttk.Scrollbar(table, orient='vertical', command=app.video_samples.yview)
    app.video_scroll.grid(row=1, column=1, sticky='ns')
    horizontal = ttk.Scrollbar(table, orient='horizontal', command=app.video_samples.xview)
    horizontal.grid(row=2, column=0, sticky='ew')
    app.video_samples.configure(yscrollcommand=app.video_scroll.set, xscrollcommand=horizontal.set)
    app.video_samples.bind('<<TreeviewSelect>>', app.select_frame)

    app.video_technical_open = False
    technical = ttk.Frame(result)
    technical.columnconfigure(0, weight=1)
    app.video_summary = ScrolledText(technical, wrap='word', font=('Segoe UI', 10), height=6, width=20)
    app.video_summary.grid(row=0, column=0, sticky='ew')
    ttk.Button(technical, text='Exportar evidência JSON da sessão', command=app.export_video).grid(row=1, column=0, sticky='w', pady=4)

    def toggle_technical():
        app.video_technical_open = not app.video_technical_open
        app.video_technical_toggle.configure(text='Evidência técnica '+('▾' if app.video_technical_open else '▸'))
        if app.video_technical_open:
            technical.grid(row=4, column=0, sticky='ew')
        else:
            technical.grid_remove()

    app.toggle_video_technical = toggle_technical
    app.video_technical_toggle = ttk.Button(result, text='Evidência técnica ▸', command=toggle_technical)
    app.video_technical_toggle.grid(row=3, column=0, sticky='w', pady=7)

    def resize(event):
        width = max(85, min(260, int(event.width*.32), int(max(150,event.height-65)*9/16)))
        app.preview_area.configure(width=width, height=int(width*16/9))
        app.preview_label.configure(wraplength=max(75,width-10))
        caption.configure(wraplength=width)
        result_label.configure(wraplength=max(200,result.winfo_width()-20))

    body.bind('<Configure>', resize)
    app.choose_video_case()
