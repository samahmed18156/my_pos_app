"""Central configuration and persistence for BKPOS AI Suite."""
from __future__ import annotations

import json
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Dict, Optional

from core.config import DB_PATH
from core.logger import logger as _bkpos_logger
from ui.theme import PALETTE, FONT, button as themed_button, entry_options
from ui.window_polish import polish_window

DEFAULT_SETTINGS: Dict[str, str] = {
    "llm_provider": "local",  # "local", "openai", "anthropic", "ollama", "custom"
    "openai_api_key": "",
    "anthropic_api_key": "",
    "ollama_endpoint": "http://localhost:11434",
    "llm_model": "gpt-4o-mini",
    "vision_camera_index": "0",
    "forecasting_service_level": "95",  # percent: 90, 95, 99
    "forecasting_lead_time_days": "7",
    "forecasting_horizon_days": "30",
    "fraud_sensitivity": "standard",  # "low", "standard", "high"
    "fraud_void_ratio_threshold": "0.15",  # 15%
    "fraud_discount_threshold": "0.20",  # 20%
    "ocr_confidence_threshold": "0.70",
}


def ensure_ai_schema(conn: Optional[sqlite3.Connection] = None) -> None:
    """Ensure the ai_settings table exists with default values."""
    should_close = False
    if conn is None:
        conn = sqlite3.connect(DB_PATH)
        should_close = True

    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        for key, val in DEFAULT_SETTINGS.items():
            conn.execute(
                "INSERT OR IGNORE INTO ai_settings (key, value) VALUES (?, ?)",
                (key, str(val))
            )
        conn.commit()
    except Exception as exc:
        _bkpos_logger.warning("Error ensuring ai_settings schema", exc_info=exc)
    finally:
        if should_close:
            conn.close()


def get_ai_setting(key: str, default: Optional[Any] = None) -> str:
    """Retrieve an AI configuration value."""
    ensure_ai_schema()
    try:
        with sqlite3.connect(DB_PATH, timeout=5) as conn:
            row = conn.execute(
                "SELECT value FROM ai_settings WHERE key = ?", (key,)
            ).fetchone()
            if row is not None:
                return row[0]
    except Exception as exc:
        _bkpos_logger.warning(f"Error reading AI setting {key}", exc_info=exc)

    return str(default if default is not None else DEFAULT_SETTINGS.get(key, ""))


def set_ai_setting(key: str, value: Any) -> None:
    """Persist an AI configuration value."""
    ensure_ai_schema()
    try:
        with sqlite3.connect(DB_PATH, timeout=5) as conn:
            conn.execute(
                "INSERT INTO ai_settings (key, value, updated_at) "
                "VALUES (?, ?, CURRENT_TIMESTAMP) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP",
                (key, str(value))
            )
            conn.commit()
    except Exception as exc:
        _bkpos_logger.warning(f"Error saving AI setting {key}", exc_info=exc)


def get_all_ai_settings() -> Dict[str, str]:
    """Retrieve all current AI configuration settings."""
    ensure_ai_schema()
    res = dict(DEFAULT_SETTINGS)
    try:
        with sqlite3.connect(DB_PATH, timeout=5) as conn:
            rows = conn.execute("SELECT key, value FROM ai_settings").fetchall()
            for k, v in rows:
                res[k] = v
    except Exception as exc:
        _bkpos_logger.warning("Error reading all AI settings", exc_info=exc)
    return res


class AISettingsDialog(tk.Toplevel):
    """Settings modal for configuring AI providers, API keys, and model parameters."""

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.parent = parent
        self.title("AI Intelligence Suite - Configuration")
        self.geometry("680x620")
        self.minsize(580, 520)
        self.configure(bg=PALETTE["bg"])
        polish_window(self, self.title())
        self.transient(parent)
        self.grab_set()

        self._entries: Dict[str, tk.Variable] = {}
        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        # Header
        header = tk.Frame(self, bg=PALETTE["nav"], height=64)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(
            header,
            text="AI INTELLIGENCE SUITE CONFIGURATION",
            font=(FONT, 14, "bold"),
            bg=PALETTE["nav"],
            fg=PALETTE["nav_text"]
        ).pack(side=tk.LEFT, padx=20, pady=16)

        # Notebook container
        container = tk.Frame(self, bg=PALETTE["bg"], padx=16, pady=16)
        container.pack(fill=tk.BOTH, expand=True)

        notebook = ttk.Notebook(container)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: LLM & Copilot
        tab_llm = tk.Frame(notebook, bg=PALETTE["surface"], padx=20, pady=16)
        notebook.add(tab_llm, text=" Copilot & NLP ")

        self._add_row(tab_llm, 0, "NLP Engine Provider:", "llm_provider",
                      kind="combobox", options=["local", "openai", "anthropic", "ollama"])
        self._add_row(tab_llm, 1, "OpenAI API Key:", "openai_api_key", kind="password")
        self._add_row(tab_llm, 2, "Anthropic API Key:", "anthropic_api_key", kind="password")
        self._add_row(tab_llm, 3, "Ollama / Local Endpoint:", "ollama_endpoint")
        self._add_row(tab_llm, 4, "Preferred Model:", "llm_model")

        lbl_info = tk.Label(
            tab_llm,
            text="* 'local' mode uses BKPOS built-in intelligent pattern NLP (zero cloud or API cost).\n"
                 "  External providers (OpenAI / Anthropic / Ollama) unlock arbitrary natural language questions.",
            font=(FONT, 9, "italic"),
            bg=PALETTE["surface"],
            fg=PALETTE["muted"],
            justify=tk.LEFT
        )
        lbl_info.grid(row=5, column=0, columnspan=2, sticky="w", pady=(14, 0))

        # Tab 2: Vision & OCR
        tab_vision = tk.Frame(notebook, bg=PALETTE["surface"], padx=20, pady=16)
        notebook.add(tab_vision, text=" Vision & OCR ")

        self._add_row(tab_vision, 0, "Webcam Device Index:", "vision_camera_index")
        self._add_row(tab_vision, 1, "OCR Match Confidence:", "ocr_confidence_threshold")

        lbl_vinfo = tk.Label(
            tab_vision,
            text="* Webcam index 0 is typically the integrated camera or primary USB scale camera.\n"
                 "* OCR uses image feature analysis with automatic fuzzy matching against your product database.",
            font=(FONT, 9, "italic"),
            bg=PALETTE["surface"],
            fg=PALETTE["muted"],
            justify=tk.LEFT
        )
        lbl_vinfo.grid(row=2, column=0, columnspan=2, sticky="w", pady=(14, 0))

        # Tab 3: Forecasting & Fraud Audit
        tab_analytics = tk.Frame(notebook, bg=PALETTE["surface"], padx=20, pady=16)
        notebook.add(tab_analytics, text=" Forecasting & Fraud ")

        self._add_row(tab_analytics, 0, "Service Level (%):", "forecasting_service_level",
                      kind="combobox", options=["90", "95", "98", "99"])
        self._add_row(tab_analytics, 1, "Supplier Lead Time (Days):", "forecasting_lead_time_days")
        self._add_row(tab_analytics, 2, "Forecast Horizon (Days):", "forecasting_horizon_days",
                      kind="combobox", options=["7", "14", "30", "60", "90"])
        self._add_row(tab_analytics, 3, "Fraud Audit Sensitivity:", "fraud_sensitivity",
                      kind="combobox", options=["low", "standard", "high"])
        self._add_row(tab_analytics, 4, "Void Alert Threshold (%):", "fraud_void_ratio_threshold")

        # Bottom buttons
        btn_bar = tk.Frame(self, bg=PALETTE["bg"], padx=16, pady=12)
        btn_bar.pack(fill=tk.X)

        themed_button(btn_bar, "SAVE CONFIGURATION", self._save_values, kind="success").pack(side=tk.RIGHT, padx=6)
        themed_button(btn_bar, "CANCEL", self.destroy, kind="secondary").pack(side=tk.RIGHT, padx=6)
        themed_button(btn_bar, "RESET TO DEFAULTS", self._reset_defaults, kind="danger").pack(side=tk.LEFT, padx=6)

    def _add_row(self, parent: tk.Widget, row: int, label_text: str, key: str,
                 kind: str = "entry", options: Optional[list] = None) -> None:
        tk.Label(
            parent,
            text=label_text,
            font=(FONT, 10, "bold"),
            bg=PALETTE["surface"],
            fg=PALETTE["text"],
            anchor="w"
        ).grid(row=row, column=0, sticky="w", padx=4, pady=8)

        var = tk.StringVar()
        self._entries[key] = var

        if kind == "combobox" and options:
            cb = ttk.Combobox(parent, textvariable=var, values=options, state="readonly", width=28)
            cb.grid(row=row, column=1, sticky="w", padx=12, pady=8)
        else:
            show = "*" if kind == "password" else ""
            ent = tk.Entry(parent, textvariable=var, show=show, width=32, **entry_options())
            ent.grid(row=row, column=1, sticky="w", padx=12, pady=8)

    def _load_values(self) -> None:
        settings = get_all_ai_settings()
        for key, var in self._entries.items():
            var.set(settings.get(key, DEFAULT_SETTINGS.get(key, "")))

    def _save_values(self) -> None:
        for key, var in self._entries.items():
            set_ai_setting(key, var.get().strip())
        messagebox.showinfo("AI Settings", "AI Suite configuration saved successfully!", parent=self)
        self.destroy()

    def _reset_defaults(self) -> None:
        if messagebox.askyesno("Reset Defaults", "Reset all AI settings to default values?", parent=self):
            for key, val in DEFAULT_SETTINGS.items():
                set_ai_setting(key, val)
            self._load_values()
