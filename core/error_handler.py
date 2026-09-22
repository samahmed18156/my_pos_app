"""BKPOS application-wide error handling helpers.

Phase 41: provide a safe boundary for unexpected exceptions without exposing
Python tracebacks to normal users. Existing business logic is intentionally
unchanged; callers can progressively route top-level actions through
handle_exception/show_user_error.
"""

from __future__ import annotations
from core.logger import logger as _bkpos_logger

import logging
import os
import traceback
from datetime import datetime
from typing import Optional

try:
    from tkinter import messagebox
except Exception:
    messagebox = None

APP_NAME = "BKPOS"

def _log_path() -> str:
    base = os.getenv("APPDATA") or os.path.expanduser("~")
    folder = os.path.join(base, APP_NAME, "logs")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "bkpos_errors.log")

def get_logger() -> logging.Logger:
    logger = logging.getLogger("bkpos.errors")
    if not logger.handlers:
        logger.setLevel(logging.ERROR)
        fh = logging.FileHandler(_log_path(), encoding="utf-8")
        fh.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        ))
        logger.addHandler(fh)
        logger.propagate = False
    return logger

def log_exception(exc: BaseException, context: str = "") -> str:
    """Log technical details and return a short reference identifier."""
    ref = datetime.now().strftime("%Y%m%d-%H%M%S")
    prefix = f"[{context}] " if context else ""
    get_logger().error(
        "%s%s\n%s",
        prefix,
        repr(exc),
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    )
    return ref

def user_message(exc: BaseException, fallback: str = "The operation could not be completed.") -> str:
    """Convert common technical failures into a user-safe message."""
    text = str(exc).lower()
    if "database is locked" in text:
        return "BKPOS is busy using the database. Please wait a moment and try again."
    if "readonly" in text or "read-only" in text or "permission denied" in text:
        return "BKPOS cannot write to its data folder. Please check folder permissions."
    if "no such table" in text or "no such column" in text:
        return "BKPOS detected a database version problem. Please contact support."
    if "disk is full" in text or "database or disk is full" in text:
        return "There is not enough disk space to complete this operation."
    return fallback

def show_user_error(message: str, title: str = "BKPOS") -> None:
    """Show a normal user-facing dialog when Tk is available."""
    if messagebox is not None:
        try:
            messagebox.showerror(title, message)
            return
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in core/error_handler.py", exc_info=exc)
    print(f"{title}: {message}")

def handle_exception(exc: BaseException, context: str = "",
                     fallback: str = "The operation could not be completed.") -> str:
    """Log technical details and display a safe message."""
    ref = log_exception(exc, context)
    msg = user_message(exc, fallback)
    show_user_error(f"{msg}\n\nReference: {ref}")
    return ref

def install_global_handler() -> None:
    """Install a last-resort handler for uncaught exceptions."""
    import sys

    def _hook(exc_type, exc_value, exc_tb):
        exc = exc_value if exc_value is not None else Exception("Unknown error")
        ref = log_exception(exc, "UNCAUGHT")
        show_user_error(
            "BKPOS encountered an unexpected error and could not complete the operation.\n\n"
            f"Reference: {ref}\n\n"
            "Your data has not been intentionally deleted."
        )

    sys.excepthook = _hook
