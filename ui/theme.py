"""BKPOS professional visual theme and UI helpers.

Presentation-only module: no business or database logic.
Elevated with modern retail fintech styling, crisp contrast, and premium typography.
"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from core.logger import logger as _bkpos_logger

PALETTE = {
    "bg": "#f1f5f9",              # Clean slate-100 canvas
    "surface": "#ffffff",         # Pure crisp white card surface
    "surface_alt": "#f8fafc",     # Subtle off-white for table alternates & inputs
    "border": "#cbd5e1",          # Refined slate-300 border
    "border_light": "#e2e8f0",    # Soft divider
    "text": "#0f172a",            # Deep slate-900 high contrast text
    "muted": "#64748b",           # Slate-500 secondary text
    "primary": "#1d4ed8",         # Royal blue 700
    "primary_hover": "#1e40af",   # Deep blue 800
    "success": "#059669",         # Emerald 600
    "success_hover": "#047857",   # Emerald 700
    "danger": "#dc2626",          # Red 600
    "danger_hover": "#b91c1c",    # Red 700
    "warning": "#d97706",         # Amber 600
    "secondary": "#475569",       # Slate 600
    "secondary_hover": "#334155", # Slate 700
    "focus": "#2563eb",           # Blue 600 focus ring
    "selected": "#dbeafe",        # Light blue 100 selection
    "nav": "#0e2a47",             # Premium Blue Knight Deep Royal Sapphire Navy (replaces harsh black #0f172a)
    "nav_alt": "#143960",         # Blue Knight Navy alternate
    "nav_text": "#ffffff",        # Bright white header text
    "nav_muted": "#93c5fd",       # Light sky blue subtitle
    "total_bg": "#0e2a47",        # Deep Blue Knight Navy for totals panel
    "total_inner": "#143960",     # Deep blue container for digital readout
    "total_text": "#10b981",      # Luminous emerald green digital readout
}

FONT = "Segoe UI"

def configure_ttk(root):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError as exc:
        _bkpos_logger.warning("Could not activate the Clam ttk theme", exc_info=exc)

    # Modern Premium Treeview
    style.configure(
        "BK.Treeview",
        background=PALETTE["surface"],
        fieldbackground=PALETTE["surface"],
        foreground=PALETTE["text"],
        rowheight=38,
        font=(FONT, 10),
        borderwidth=0,
        relief="flat"
    )
    style.configure(
        "BK.Treeview.Heading",
        background="#e2e8f0",
        foreground="#1e293b",
        font=(FONT, 10, "bold"),
        padding=(12, 10),
        relief="flat",
        borderwidth=0
    )
    style.map(
        "BK.Treeview",
        background=[("selected", PALETTE["selected"])],
        foreground=[("selected", PALETTE["primary"])]
    )
    style.map(
        "BK.Treeview.Heading",
        background=[("active", "#cbd5e1")]
    )

    style.configure(
        "BK.Horizontal.TProgressbar",
        troughcolor="#e2e8f0",
        background=PALETTE["primary"],
        borderwidth=0,
        thickness=10
    )
    style.configure(
        "BK.TCombobox",
        fieldbackground=PALETTE["surface"],
        background=PALETTE["surface"],
        foreground=PALETTE["text"],
        padding=6,
        arrowsize=14
    )
    return style

def button(parent, text, command, kind="primary", **kwargs):
    colors = {
        "primary": (PALETTE["primary"], PALETTE["primary_hover"], "#ffffff"),
        "success": (PALETTE["success"], PALETTE["success_hover"], "#ffffff"),
        "danger": (PALETTE["danger"], PALETTE["danger_hover"], "#ffffff"),
        "secondary": (PALETTE["secondary"], PALETTE["secondary_hover"], "#ffffff"),
        "warning": (PALETTE["warning"], "#b45309", "#ffffff"),
        "dark": (PALETTE["nav"], "#1e293b", "#ffffff"),
    }
    bg, hover, fg = colors.get(kind, colors["primary"])
    options = {
        "font": (FONT, 10, "bold"),
        "bg": bg,
        "fg": fg,
        "activebackground": hover,
        "activeforeground": fg,
        "relief": tk.FLAT,
        "bd": 0,
        "cursor": "hand2",
        "padx": 16,
        "pady": 9,
        "highlightthickness": 0,
        "takefocus": 1
    }
    options.update(kwargs)
    btn = tk.Button(parent, text=text, command=command, **options)

    def enter(_):
        if btn["state"] != "disabled":
            btn.configure(bg=hover)

    def leave(_):
        btn.configure(bg=bg)

    btn.bind("<Enter>", enter, add="+")
    btn.bind("<Leave>", leave, add="+")
    return btn

def entry_options(**kwargs):
    options = {
        "font": (FONT, 12),
        "bd": 1,
        "relief": tk.SOLID,
        "highlightthickness": 2,
        "highlightcolor": PALETTE["focus"],
        "highlightbackground": PALETTE["border"],
        "insertbackground": PALETTE["text"]
    }
    options.update(kwargs)
    return options

