"""BKPOS Phase 71 — consistent desktop window presentation."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ui.theme import PALETTE, configure_ttk
from core.logger import logger as _bkpos_logger

APP_PREFIX = "BKPOS • "
APP_FONT = "Segoe UI"


def polished_title(title: str) -> str:
    """Return a consistent BKPOS-prefixed window title without double-prefixing."""
    text = (title or "BKPOS").strip()
    if text == "BKPOS" or text.startswith(APP_PREFIX):
        return text
    return APP_PREFIX + text


def polish_window(window: tk.Misc, title: str | None = None, *, escape_close: bool = True) -> tk.Misc:
    """Apply the shared BKPOS visual treatment to an existing Tk window."""
    if title is not None:
        window.title(polished_title(title))
    else:
        try:
            current = window.title()
            if current:
                window.title(polished_title(current))
        except tk.TclError as exc:
            _bkpos_logger.debug("Window title unavailable during polish: %s", exc)

    try:
        window.configure(bg=PALETTE["bg"])
    except tk.TclError as exc:
        _bkpos_logger.debug("Window background unavailable during polish: %s", exc)

    try:
        configure_ttk(window)
    except tk.TclError as exc:
        _bkpos_logger.debug("TTK configuration unavailable during polish: %s", exc)

    if escape_close:
        try:
            window.bind("<Escape>", lambda _event: window.destroy(), add="+")
        except tk.TclError as exc:
            _bkpos_logger.debug("Escape binding unavailable during polish: %s", exc)
    return window


def style_section_label(parent, text: str) -> tk.Label:
    """Create a standard small uppercase section label."""
    return tk.Label(
        parent,
        text=(text or "").upper(),
        font=(APP_FONT, 9, "bold"),
        bg=PALETTE["bg"],
        fg=PALETTE["primary"],
        anchor="w",
    )


def style_status_label(parent, text: str = "") -> tk.Label:
    """Create a standard muted status label."""
    return tk.Label(
        parent,
        text=text,
        font=(APP_FONT, 9),
        bg=PALETTE["bg"],
        fg=PALETTE["muted"],
        anchor="w",
    )
