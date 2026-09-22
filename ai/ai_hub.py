"""Central Hub and POS Integration for the BKPOS AI Intelligence Suite.

Integrates all 5 AI modules (Copilot, OCR GRN, Vision Produce, ML Forecasting,
and Fraud Anomaly Detection) directly into the main POS desktop window, menus,
and keyboard shortcuts.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Any, Dict, Optional

from core.logger import logger as _bkpos_logger
from ai.config import AISettingsDialog, ensure_ai_schema
from ai.copilot import AICopilotWindow
from ai.ocr_grn import AIInvoiceOCRWindow
from ai.vision_checkout import ProduceVisionCheckoutWindow
from ai.forecasting import AIForecastingWindow
from ai.fraud_detection import AIFraudAnomalyWindow
from ui.theme import PALETTE, FONT, button as themed_button
from ui.window_polish import polish_window


class AISuiteWindow(tk.Toplevel):
    """Central Executive Dashboard for launching all 5 AI POS capabilities."""

    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self.parent = parent
        self.title("BKPOS AI Intelligence Suite - Executive Control Center")
        self.geometry("1100x700")
        self.minsize(920, 580)
        self.configure(bg=PALETTE["bg"])
        polish_window(self, self.title())

        ensure_ai_schema()
        self._build_ui()

    def _build_ui(self) -> None:
        # Header
        header = tk.Frame(self, bg=PALETTE["nav"], height=74)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        brand = tk.Frame(header, bg=PALETTE["nav"])
        brand.pack(side=tk.LEFT, padx=20, pady=14)

        tk.Label(
            brand,
            text="🧠 BKPOS ENTERPRISE AI SUITE",
            font=(FONT, 16, "bold"),
            bg=PALETTE["nav"],
            fg=PALETTE["nav_text"]
        ).pack(anchor="w")

        tk.Label(
            brand,
            text="Active AI Engines: Natural Language Copilot • Vision Checkout • Auto-GRN • ML Forecasting • Loss Prevention",
            font=(FONT, 9),
            bg=PALETTE["nav"],
            fg=PALETTE["nav_muted"]
        ).pack(anchor="w", pady=(2, 0))

        themed_button(header, "⚙️ AI Settings", lambda: AISettingsDialog(self), kind="secondary").pack(side=tk.RIGHT, padx=20, pady=18)

        # Body grid of AI tools
        body = tk.Frame(self, bg=PALETTE["bg"], padx=20, pady=16)
        body.pack(fill=tk.BOTH, expand=True)

        tools = [
            (
                "🤖 AI STORE COPILOT",
                "Natural Language Assistant [F10]",
                "Ask store questions in plain English. Translates natural language into safe read-only SQL queries to analyze inventory, revenue, sales, and cashier performance.",
                lambda: AICopilotWindow(self.parent),
                "OPEN COPILOT 🚀",
                PALETTE["primary"]
            ),
            (
                "📄 AI INVOICE & RECEIPT OCR",
                "Automated Supplier GRN Ingestion",
                "Parses supplier invoices and delivery slips. Extracts line items, quantities, and unit costs with automatic fuzzy product matching and 1-click stock receiving.",
                lambda: AIInvoiceOCRWindow(self.parent),
                "LAUNCH AUTO-GRN 📦",
                PALETTE["primary"]
            ),
            (
                "🍎 AI VISION CHECKOUT",
                "Barcode-Free Produce & Bakery [F4]",
                "Identifies unpackaged fruits, vegetables, and loose bakery items via camera feature extraction. Calculates weight-based pricing and adds directly to cashier cart.",
                lambda: ProduceVisionCheckoutWindow(self.parent),
                "OPEN VISION CAMERA 📷",
                PALETTE["primary"]
            ),
            (
                "📈 ML DEMAND FORECASTING",
                "Time-Series Predictive Reordering",
                "Holt-Winters exponential smoothing and Scikit-Learn regression with day-of-week seasonality. Generates dynamic safety stock and 1-click draft Purchase Orders.",
                lambda: AIForecastingWindow(self.parent),
                "RUN FORECAST 📊",
                PALETTE["primary"]
            ),
            (
                "🛡️ AI FRAUD & LOSS AUDIT",
                "Cashier Behavioral Anomaly Monitor",
                "Monitors cashier void bursts, price overrides, off-hours sales, and phantom refunds. Computes multi-dimensional anomaly scores to eliminate retail shrinkage.",
                lambda: AIFraudAnomalyWindow(self.parent),
                "OPEN FRAUD AUDITOR 🔍",
                PALETTE["primary"]
            ),
            (
                "⚙️ AI CONFIGURATION",
                "Model & Hardware Provider Setup",
                "Configure LLM endpoints (Local NLP, OpenAI, Anthropic, Ollama), webcam video input, service levels, and fraud sensitivity thresholds.",
                lambda: AISettingsDialog(self),
                "CONFIGURE SUITE ⚙️",
                PALETTE["secondary"]
            ),
        ]

        for i, (title, subtitle, desc, cmd, btn_label, col) in enumerate(tools):
            row, c_idx = divmod(i, 3)
            card = tk.Frame(body, bg=PALETTE["surface"], bd=1, relief=tk.SOLID, padx=14, pady=14)
            card.grid(row=row, column=c_idx, sticky="nsew", padx=8, pady=8)
            body.grid_columnconfigure(c_idx, weight=1)
            body.grid_rowconfigure(row, weight=1)

            # Card Header
            tk.Label(card, text=title, font=(FONT, 11, "bold"), bg=PALETTE["surface"], fg=col, anchor="w").pack(fill=tk.X)
            tk.Label(card, text=subtitle, font=(FONT, 9, "bold"), bg=PALETTE["surface"], fg=PALETTE["muted"], anchor="w").pack(fill=tk.X, pady=(2, 6))

            # Description
            tk.Label(card, text=desc, font=(FONT, 9), bg=PALETTE["surface"], fg=PALETTE["text"], justify=tk.LEFT, wraplength=280, anchor="nw").pack(fill=tk.BOTH, expand=True, pady=(0, 10))

            # Action button
            themed_button(card, btn_label, cmd, kind="primary" if col != PALETTE["secondary"] else "secondary").pack(anchor="e")


def install(app_cls: Any) -> Any:
    """Install the AI Intelligence Suite into the FamilySupermarketPOS application class."""

    # 1. Enhance Menu Bar with "AI Suite"
    old_create_menu_bar = getattr(app_cls, "create_menu_bar", None)

    def create_menu_bar_with_ai(self: Any) -> None:
        if old_create_menu_bar:
            old_create_menu_bar(self)

        try:
            mb = self.nametowidget(self["menu"])
            # Create AI Suite Menu
            ai_menu = tk.Menu(mb, tearoff=0)
            ai_menu.add_command(
                label="AI Store Copilot (Natural Language)    F10",
                command=lambda: AICopilotWindow(self)
            )
            ai_menu.add_command(
                label="AI Invoice & Receipt OCR (Auto-GRN)",
                command=lambda: AIInvoiceOCRWindow(self)
            )
            ai_menu.add_command(
                label="AI Produce & Bakery Recognition         F4",
                command=lambda: ProduceVisionCheckoutWindow(self)
            )
            ai_menu.add_separator()
            ai_menu.add_command(
                label="AI Demand Forecasting & Smart Reorder",
                command=lambda: AIForecastingWindow(self)
            )
            ai_menu.add_command(
                label="AI Fraud & Loss Anomaly Monitor",
                command=lambda: AIFraudAnomalyWindow(self)
            )
            ai_menu.add_separator()
            ai_menu.add_command(
                label="AI Suite Control Center",
                command=lambda: AISuiteWindow(self)
            )
            ai_menu.add_command(
                label="AI Suite Configuration",
                command=lambda: AISettingsDialog(self)
            )

            mb.add_cascade(label="AI Suite", menu=ai_menu)
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception adding AI Suite to menu bar", exc_info=exc)

    app_cls.create_menu_bar = create_menu_bar_with_ai

    # 2. Add hotkeys to POS window
    old_init = app_cls.__init__

    def init_with_ai(self: Any, *args: Any, **kwargs: Any) -> None:
        old_init(self, *args, **kwargs)
        try:
            # Bind F10 for Copilot
            self.bind("<F10>", lambda e: AICopilotWindow(self))
            # Bind F4 for Produce Vision
            self.bind("<F4>", lambda e: ProduceVisionCheckoutWindow(self))

            # Add quick access buttons to POS header or action bar if present
            if hasattr(self, "pos_screen"):
                # Check for header brand
                for child in self.pos_screen.winfo_children():
                    if isinstance(child, tk.Frame) and child.cget("height") == 88:
                        # Add quick AI buttons to header right
                        ai_bar = tk.Frame(child, bg=child.cget("bg"))
                        ai_bar.pack(side=tk.RIGHT, padx=10, pady=12)

                        btn_copilot = tk.Button(
                            ai_bar,
                            text="🤖 AI Copilot (F10)",
                            font=(FONT, 9, "bold"),
                            bg="#3b82f6",
                            fg="white",
                            activebackground="#2563eb",
                            activeforeground="white",
                            bd=0,
                            padx=10,
                            pady=6,
                            cursor="hand2",
                            command=lambda: AICopilotWindow(self)
                        )
                        btn_copilot.pack(side=tk.LEFT, padx=3)

                        btn_vis = tk.Button(
                            ai_bar,
                            text="🍎 Produce Vision (F4)",
                            font=(FONT, 9, "bold"),
                            bg="#10b981",
                            fg="white",
                            activebackground="#059669",
                            activeforeground="white",
                            bd=0,
                            padx=10,
                            pady=6,
                            cursor="hand2",
                            command=lambda: ProduceVisionCheckoutWindow(self)
                        )
                        btn_vis.pack(side=tk.LEFT, padx=3)
                        break
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in AI Suite POS initialization", exc_info=exc)

    app_cls.__init__ = init_with_ai

    # Provide direct open methods on the POS class
    app_cls.open_ai_copilot = lambda self: AICopilotWindow(self)
    app_cls.open_ai_ocr = lambda self: AIInvoiceOCRWindow(self)
    app_cls.open_ai_vision = lambda self: ProduceVisionCheckoutWindow(self)
    app_cls.open_ai_forecasting = lambda self: AIForecastingWindow(self)
    app_cls.open_ai_fraud_monitor = lambda self: AIFraudAnomalyWindow(self)
    app_cls.open_ai_suite = lambda self: AISuiteWindow(self)

    return app_cls
