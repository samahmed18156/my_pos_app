"""BKPOS professional visual theme and UI helpers.

Presentation-only module: no business or database logic.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from core.logger import logger as _bkpos_logger

PALETTE = {
    "bg": "#f3f6fa",
    "surface": "#ffffff",
    "surface_alt": "#f8fafc",
    "border": "#d9e2ec",
    "text": "#172033",
    "muted": "#64748b",
    "primary": "#1f5fae",
    "primary_hover": "#174a8b",
    "success": "#0f8a5f",
    "success_hover": "#0b6f4c",
    "danger": "#c63b3b",
    "danger_hover": "#a72e2e",
    "warning": "#b7791f",
    "secondary": "#64748b",
    "secondary_hover": "#475569",
    "focus": "#3b82f6",
    "selected": "#dbeafe",
    "nav": "#10233f",
    "nav_alt": "#18365f",
    "nav_text": "#e8f0fb",
    "nav_muted": "#9fb2ca",
}

FONT = "Segoe UI"

def configure_ttk(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError as exc:
        _bkpos_logger.warning("Could not activate the Clam ttk theme", exc_info=exc)
    style.configure("BK.Treeview", background=PALETTE["surface"], fieldbackground=PALETTE["surface"], foreground=PALETTE["text"], rowheight=36, font=(FONT, 10), borderwidth=0)
    style.configure("BK.Treeview.Heading", background="#eef3f8", foreground=PALETTE["text"], font=(FONT, 10, "bold"), padding=(10, 10), relief="flat")
    style.map("BK.Treeview", background=[("selected", PALETTE["selected"])], foreground=[("selected", PALETTE["text"])])
    style.configure("BK.Horizontal.TProgressbar", troughcolor="#e5ebf2", background=PALETTE["primary"], borderwidth=0, thickness=8)
    style.configure("BK.TCombobox", fieldbackground=PALETTE["surface"], background=PALETTE["surface"], foreground=PALETTE["text"], padding=6)
    return style

def button(parent, text, command, kind="primary", **kwargs):
    colors={"primary":(PALETTE["primary"],PALETTE["primary_hover"],"white"),"success":(PALETTE["success"],PALETTE["success_hover"],"white"),"danger":(PALETTE["danger"],PALETTE["danger_hover"],"white"),"secondary":(PALETTE["secondary"],PALETTE["secondary_hover"],"white")}
    bg,hover,fg=colors.get(kind,colors["primary"])
    options={"font":(FONT,10,"bold"),"bg":bg,"fg":fg,"activebackground":hover,"activeforeground":fg,"relief":tk.FLAT,"bd":0,"cursor":"hand2","padx":14,"pady":8,"highlightthickness":0,"takefocus":1}
    options.update(kwargs)
    btn=tk.Button(parent,text=text,command=command,**options)
    def enter(_):
        if btn["state"]!="disabled": btn.configure(bg=hover)
    def leave(_): btn.configure(bg=bg)
    btn.bind("<Enter>",enter,add="+")
    btn.bind("<Leave>",leave,add="+")
    return btn

def entry_options(**kwargs):
    options={"font":(FONT,12),"bd":1,"relief":tk.SOLID,"highlightthickness":2,"highlightcolor":PALETTE["focus"],"highlightbackground":PALETTE["border"],"insertbackground":PALETTE["text"]}
    options.update(kwargs)
    return options
