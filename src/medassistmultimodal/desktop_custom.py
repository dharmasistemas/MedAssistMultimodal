"""CustomTkinter presentation over the approved workflow, with native fallbacks."""
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
import os

import customtkinter as ctk

from medassistmultimodal.desktop_simplified import SimplifiedApp


COLORS = dict(background='#171a21', panel='#232831', field='#141820', text='#edf1f7',
              muted='#b6c0ce', border='#414b5b', accent='#1f538d', active='#3478aa',
              button_border='#ffffff', hover='#286aa8', disabled='#313b49')

FONTS = dict(control=('Segoe UI',12,'bold'),heading=('Segoe UI',13,'bold'),
             text=('Segoe UI',12),button=('Segoe UI',14,'bold'),tab=('Segoe UI',12,'bold'),
             brand=('Segoe UI',26,'bold'),subtitle=('Segoe UI',14),icon=('Segoe UI Symbol',18))
TAB_PADDING = (20,10)
VIDEO_INPUT_WIDTH = 350
VIDEO_COLUMN_WIDTHS = dict(frame=75,time=105,elbow=125,arm=155,quality=205)


def work_area(root):
    if os.name == 'nt':
        import ctypes
        from ctypes.wintypes import RECT
        rect = RECT()
        if ctypes.windll.user32.SystemParametersInfoW(48,0,ctypes.byref(rect),0):
            return rect.left,rect.top,rect.right,rect.bottom
    return 0,0,root.winfo_screenwidth(),root.winfo_screenheight()


def configure_appearance():
    ctk.set_appearance_mode('dark')
    ctk.set_default_color_theme('blue')


class OpaqueCTk(ctk.CTk):
    """The app has no translucent mode; keep DPI transitions opaque on Windows.

    CustomTkinter temporarily sets alpha to .15 before scaling callbacks and
    restores it afterwards without a finally block. A callback error can leave
    the window translucent. Do not modify the global tracker or DPI settings.
    """
    def attributes(self, *args):
        if len(args) >= 2 and len(args) % 2 == 0:
            values = list(args)
            for i in range(0, len(values), 2):
                if values[i] == '-alpha':
                    values[i+1] = 1.0
            args = tuple(values)
        return super().attributes(*args)

    wm_attributes = attributes


class CustomApp(SimplifiedApp):
    """Appearance only: original widgets retain commands, variables and validation."""

    def __init__(self, root, **kwargs):
        self.custom_buttons = []
        self._custom_disabled = []
        self.player_tooltips = []
        super().__init__(root, **kwargs)
        self._style_native_widgets()
        self._build_custom_header()
        self._adapt_buttons()
        self._finish_controls()
        root.title('MedAssistMultimodal — POC acadêmica')
        # CTk applies monitor DPI to its logical geometry; leave room for title/task bars.
        if isinstance(root,(ctk.CTk,ctk.CTkToplevel)):
            root.geometry('1180x740+20+20')
            root.update_idletasks()
            scale = root.winfo_width()/1180
            left,top,right,bottom = work_area(root)
            width = min(1180,int((right-left-80)/scale))
            height = min(740,int((bottom-top-100)/scale))
            root.minsize(min(900,width),min(600,height))
            root.geometry(f'{width}x{height}+20+20')
        self.maximize_after_id = root.after_idle(self._maximize_window)

    def _style_native_widgets(self):
        c = COLORS
        if isinstance(self.root,(ctk.CTk,ctk.CTkToplevel)):
            self.root.configure(fg_color=c['background'])
        else:
            self.root.configure(background=c['background'])
        style = ttk.Style(self.root)
        style.theme_use('clam')
        style.configure('MAM.TFrame',background=c['panel'])
        style.configure('MAM.TLabel',background=c['panel'],foreground=c['text'],font=FONTS['control'])
        style.configure('MAM.TEntry',fieldbackground=c['field'],foreground=c['text'],insertcolor=c['text'],bordercolor=c['border'],padding=6)
        style.configure('MAM.TCombobox',fieldbackground=c['field'],background=c['accent'],foreground=c['text'],arrowcolor=c['text'],bordercolor=c['border'],padding=5)
        style.map('MAM.TCombobox',fieldbackground=[('disabled',c['disabled']),('readonly',c['field'])],foreground=[('disabled',c['muted']),('readonly',c['text'])],selectbackground=[('readonly',c['field'])],selectforeground=[('readonly',c['text'])])
        style.configure('MAM.TCheckbutton',background=c['panel'],foreground=c['text'],font=FONTS['control'])
        style.map('MAM.TCheckbutton',background=[('active',c['panel'])],foreground=[('disabled',c['muted'])])
        style.configure('MAM.TNotebook',background=c['background'],borderwidth=0,bordercolor=c['border'],lightcolor=c['border'],darkcolor=c['border'],tabmargins=(0,6,0,0))
        style.configure('MAM.TNotebook.Tab',background=c['panel'],foreground=c['muted'],bordercolor=c['border'],lightcolor=c['border'],darkcolor=c['border'],padding=TAB_PADDING,font=FONTS['tab'])
        style.map('MAM.TNotebook.Tab',padding=[('selected',TAB_PADDING),('!selected',TAB_PADDING)],expand=[('selected',(0,0,0,0)),('!selected',(0,0,0,0))],background=[('selected',c['active']),('active',c['hover'])],foreground=[('selected',c['text']),('active',c['text'])])
        style.configure('MAM.Treeview',background=c['field'],fieldbackground=c['field'],foreground=c['text'],bordercolor=c['border'],rowheight=33,font=FONTS['control'])
        style.configure('MAM.Treeview.Heading',background=c['active'],foreground=c['text'],bordercolor=c['border'],lightcolor=c['border'],darkcolor=c['border'],font=FONTS['control'],padding=7)
        style.map('MAM.Treeview',background=[('selected',c['accent'])],foreground=[('selected',c['text'])])
        style.map('MAM.Treeview.Heading',background=[('active',c['hover'])])
        style.configure('MAM.TPanedwindow',background=c['background'])
        style.configure('MAM.TSeparator',background=c['border'])
        for orientation in ('Vertical','Horizontal'):
            style.configure(f'MAM.{orientation}.TScrollbar',background=c['border'],troughcolor=c['panel'],arrowcolor=c['text'],borderwidth=0)
        style.configure('MAM.Horizontal.TProgressbar',background=c['accent'],troughcolor=c['field'],borderwidth=0)
        self.root.option_add('*TCombobox*Listbox.background',c['field'])
        self.root.option_add('*TCombobox*Listbox.foreground',c['text'])
        self.root.option_add('*TCombobox*Listbox.selectBackground',c['accent'])
        self.root.option_add('*TCombobox*Listbox.selectForeground',c['text'])
        self.root.option_add('*TCombobox*Listbox.font',FONTS['control'])
        def visit(widget):
            for child in widget.winfo_children():
                if isinstance(child,ttk.Widget):
                    name = child.winfo_class()
                    if name in ('TFrame','TLabel','TEntry','TCombobox','TCheckbutton','TNotebook','Treeview','TPanedwindow','TSeparator'):
                        child.configure(style='MAM.'+name)
                        if name in ('TEntry','TCombobox'):
                            child.configure(font=FONTS['control'])
                        elif name=='TLabel':
                            previous=tkfont.Font(self.root,font=child.cget('font') or ('Segoe UI',10))
                            child.configure(font=FONTS['heading'] if previous.actual('weight')=='bold' else FONTS['control'])
                    elif name == 'TScrollbar':
                        child.configure(style='MAM.'+str(child.cget('orient')).capitalize()+'.TScrollbar')
                    elif name == 'TProgressbar':
                        child.configure(style='MAM.Horizontal.TProgressbar')
                elif isinstance(child,tk.Text):
                    child.configure(background=c['field'],foreground=c['text'],insertbackground=c['text'],
                                    selectbackground=c['accent'],selectforeground=c['text'],relief='flat',highlightthickness=0,font=FONTS['text'])
                elif isinstance(child,tk.Canvas):
                    child.configure(background=c['panel'],highlightthickness=0)
                elif isinstance(child,(tk.Frame,tk.Label,tk.Scrollbar)):
                    child.configure(background=c['panel'])
                    if isinstance(child,tk.Label):
                        child.configure(foreground=c['text'])
                    if isinstance(child,tk.Scrollbar):
                        child.configure(activebackground=c['accent'],troughcolor=c['field'])
                visit(child)
        visit(self.root)

    def _build_custom_header(self):
        # The first two static labels are the original brand; leave status/variables intact.
        labels = [w for w in self.root.winfo_children() if isinstance(w,ttk.Label)]
        for widget in labels:
            if str(widget.cget('text')).startswith(('MedAssistMultimodal','POC acadêmica')):
                widget.pack_forget()
        self.brand = ctk.CTkFrame(self.root,fg_color=COLORS['background'],corner_radius=0)
        status = next(w for w in labels if str(w.cget('textvariable'))==str(self.status))
        self.brand.pack(fill='x',padx=14,pady=(12,6),before=status)
        ctk.CTkLabel(self.brand,text='MedAssistMultimodal',font=FONTS['brand'],text_color=COLORS['text']).pack(anchor='w')
        ctk.CTkLabel(self.brand,text='POC acadêmica · Apoio à revisão profissional · Sem diagnóstico',font=FONTS['subtitle'],text_color=COLORS['muted']).pack(anchor='w')

    def _adapt_buttons(self):
        def collect(widget):
            result = []
            for child in widget.winfo_children():
                if isinstance(child,ttk.Button) and child.winfo_manager() in ('pack','grid'):
                    result.append(child)
                result.extend(collect(child))
            return result
        owners = (self,self.audio_panel,self.anomaly_panel,self.review_panel)
        packed = []
        for original in collect(self.root):
            manager = original.winfo_manager()
            options = original.pack_info() if manager=='pack' else original.grid_info()
            command = str(original.cget('command'))
            text = str(original.cget('text'))
            primary = text in ('Analisar vídeo','Processar áudio','Analisar cenário','Gerar prévia','Registrar como revisado','Exportar TXT e JSON')
            # Keep the Tcl command owner alive; the replacement invokes the same validated callback.
            button = ctk.CTkButton(original.master,text=text,font=FONTS['button'],height=34,
                width=max(65,int(tkfont.Font(self.root,font=FONTS['control']).measure(text))+28),corner_radius=7,
                fg_color=COLORS['accent'] if primary else COLORS['panel'],hover_color=COLORS['hover'],
                border_width=1,border_color=COLORS['button_border'],text_color=COLORS['text'],
                text_color_disabled=COLORS['muted'],state=str(original.cget('state')),
                bg_color=COLORS['panel'],command=lambda cmd=command:self.root.tk.call(cmd))
            if manager=='pack':
                siblings = list(self.root.nametowidget(str(options['in'])).pack_slaves())
                position = siblings.index(original)
                original.pack_forget()
                if position+1<len(siblings):
                    options['before']=siblings[position+1]
                button.pack(**options)
                packed.append((button,options.copy()))
            else:
                original.grid_remove();button.grid(**options)
            button.lift()
            self.custom_buttons.append(button)
            for owner in owners:
                for name,value in tuple(vars(owner).items()):
                    if value is original:
                        setattr(owner,name,button)

        # Initial insertion uses `before` to preserve order. That sibling may be
        # another legacy button replaced later. CTk replays pack arguments on
        # DPI changes, so cache only stable arguments after all insertions finish.
        # Reconfiguring an already packed widget without before/after keeps order.
        for button, options in packed:
            options.pop('before',None)
            options.pop('after',None)
            button.pack(**options)

    def _maximize_window(self):
        self.maximize_after_id = None
        try:
            self.root.state('zoomed')
        except tk.TclError:
            self.root.attributes('-zoomed',True)

    def _finish_controls(self):
        from medassistmultimodal.desktop_tooltip import ControlTooltip
        self.workspace_button = next(b for b in self.custom_buttons if b.cget('text')=='Área de trabalho ▸')
        self.history_button = next(b for b in self.custom_buttons if b.cget('text')=='Histórico de sessões ▸')
        self._highlight_tools()
        for text,icon in (('Ouvir','▶'),('Pausar','⏸'),('Parar','■')):
            button=next(b for b in self.custom_buttons if b.cget('text')==text)
            button.configure(text=icon,font=FONTS['icon'],width=60)
            self.player_tooltips.append(ControlTooltip(button,text))
        canvas=self.video_inputs.master
        canvas.configure(width=VIDEO_INPUT_WIDTH)
        for col,width in VIDEO_COLUMN_WIDTHS.items():
            self.video_samples.column(col,width=width,minwidth=width,stretch=False)
        self.video_samples.master.grid_configure(sticky='nsw')
        self.video_inputs.bind('<Configure>',self._wrap_video_labels,add='+')
        self.video_result_body.bind('<Configure>',self._resize_video)
        self.tools.bind('<Configure>',self._wrap_tool_hint,add='+')
        self.events.column('status',width=165,minwidth=155,stretch=False)

    def _wrap_video_labels(self,event):
        for widget in self.video_inputs.winfo_children():
            if isinstance(widget,ttk.Label):
                width=max(160,event.width-24)
                if int(widget.cget('wraplength') or 0)!=width:
                    widget.configure(wraplength=width)

    def _resize_video(self,event):
        width=max(100,min(380,int(event.width*.38),int(max(180,event.height-90)*9/16)))
        self.preview_area.configure(width=width,height=int(width*16/9))
        self.preview_label.configure(wraplength=max(90,width-10))
        caption=self.preview_area.master.grid_slaves(row=1,column=0)[0]
        caption.configure(wraplength=width)
        result=self.video_result_body.master
        for widget in result.grid_slaves(row=1,column=0):
            if isinstance(widget,ttk.Label):widget.configure(wraplength=max(200,result.winfo_width()-20))

    def _wrap_tool_hint(self,event):
        labels=[w for w in self.tools.winfo_children() if isinstance(w,ttk.Label)]
        if labels:
            width=max(140,event.width-self.workspace_button.winfo_width()-self.history_button.winfo_width()-55)
            if int(labels[0].cget('wraplength') or 0)!=width:
                labels[0].configure(wraplength=width)

    def _highlight_tools(self):
        if not hasattr(self,'workspace_button'):return
        for button,opened,title in ((self.workspace_button,self.workspace_open,'Área de trabalho'),
                                    (self.history_button,self.history_open,'Histórico de sessões')):
            button.configure(fg_color=COLORS['active'] if opened else COLORS['panel'],text=title+(' ▾' if opened else ' ▸'))

    def toggle_workspace(self):
        super().toggle_workspace()
        if self.workspace_open:
            if self.history_open:super().toggle_history()
            self.database_bar.pack_configure(before=self.tabs.master)
        self._highlight_tools()

    def toggle_history(self):
        super().toggle_history()
        if self.history_open and self.workspace_open:super().toggle_workspace()
        self._highlight_tools()

    def request_close(self):
        for tip in self.player_tooltips:tip.hide()
        if self.maximize_after_id is not None:
            self.root.after_cancel(self.maximize_after_id);self.maximize_after_id=None
        super().request_close()

    def _set_busy(self,busy):
        super()._set_busy(busy)
        if busy:
            self._custom_disabled=[(button,button.cget('state')) for button in self.custom_buttons]
            for button,_ in self._custom_disabled:
                button.configure(state='disabled')
        else:
            for button,state in self._custom_disabled:
                if button.winfo_exists():
                    button.configure(state=state)
            self._custom_disabled=[]
