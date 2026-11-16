"""Local hover hints; no command replacement or external dependency."""
import tkinter as tk
from tkinter import ttk


class ControlTooltip:
    def __init__(self,widget,text,delay=500):
        self.widget,self.text,self.delay = widget,text,delay
        self.after_id = None
        self.window = None
        widget.bind('<Enter>',self.schedule,add=True)
        widget.bind('<Leave>',self.hide,add=True)
        widget.bind('<ButtonPress-1>',self.hide,add=True)
        widget.bind('<Destroy>',self.hide,add=True)

    def schedule(self,_event=None):
        self.hide()
        self.after_id = self.widget.after(self.delay,self.show)

    def show(self):
        self.after_id = None
        if not self.widget.winfo_exists() or not self.widget.winfo_ismapped():
            return
        if self.window is not None:
            return
        tip = tk.Toplevel(self.widget.winfo_toplevel())
        tip.withdraw();tip.overrideredirect(True)
        ttk.Label(tip,text=self.text,font=('Segoe UI',12),padding=7,
                  background='#141820',foreground='#ffffff',relief='solid',borderwidth=1).pack()
        x=self.widget.winfo_rootx()+8;y=self.widget.winfo_rooty()+self.widget.winfo_height()+6
        tip.geometry(f'+{x}+{y}');tip.deiconify()
        self.window = tip

    def hide(self,_event=None):
        if self.after_id is not None:
            try:self.widget.after_cancel(self.after_id)
            except tk.TclError:pass
            self.after_id = None
        if self.window is not None:
            try:self.window.destroy()
            except tk.TclError:pass
            self.window = None
