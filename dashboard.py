"""BKPOS-style home dashboard.

The dashboard is presentation-only: it does not replace or duplicate any POS
workflow. The existing invoice/POS screen remains intact and is opened by
NEW SALE / NEW INVOICE. Business functions continue to use the existing
modules and database.
"""
from core.logger import logger as _bkpos_logger
import sqlite3
import tkinter as tk
from tkinter import messagebox

from core.config import DB_PATH
from ui.theme import PALETTE
DB_NAME = DB_PATH


def _money(value):
    return f"R {float(value or 0):,.2f}"


def _db_metrics():
    c = sqlite3.connect(DB_NAME)
    try:
        today = c.execute(
            "SELECT COALESCE(SUM(total_amount),0), COUNT(*) "
            "FROM sales_history WHERE date(timestamp)=date('now') AND COALESCE(voided,0)=0"
        ).fetchone()
        debtors = 0.0
        try:
            debtors = c.execute(
                "SELECT COALESCE(SUM(debit-credit),0) "
                "FROM customer_account_transactions"
            ).fetchone()[0] or 0
        except sqlite3.Error:
            _bkpos_logger.warning("Suppressed exception in dashboard.py", exc_info=exc)
        low_stock = 0
        try:
            low_stock = c.execute(
                "SELECT COUNT(*) FROM products "
                "WHERE COALESCE(soh,0) <= COALESCE(reorder_level,5)"
            ).fetchone()[0]
        except sqlite3.Error:
            try:
                low_stock = c.execute(
                    "SELECT COUNT(*) FROM products WHERE COALESCE(soh,0) <= 5"
                ).fetchone()[0]
            except sqlite3.Error:
                low_stock = 0
        return float(today[0] or 0), int(today[1] or 0), float(debtors), int(low_stock)
    finally:
        c.close()


def _tile(parent, title, subtitle, command, accent, row, col):
    card = tk.Frame(parent, bg="#ffffff", bd=1, relief=tk.SOLID, cursor="hand2")
    card.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)
    parent.grid_columnconfigure(col, weight=1)

    strip = tk.Frame(card, bg=accent, width=7)
    strip.pack(side="left", fill="y")

    body = tk.Frame(card, bg="#ffffff", padx=15, pady=13)
    body.pack(fill="both", expand=True)
    lbl = tk.Label(body, text=title, font=("Segoe UI", 13, "bold"),
                   bg="#ffffff", fg="#17212b", anchor="w")
    lbl.pack(fill="x")
    sub = tk.Label(body, text=subtitle, font=("Segoe UI", 9),
                   bg="#ffffff", fg="#64748b", anchor="w", justify="left")
    sub.pack(fill="x", pady=(5, 0))

    for w in (card, strip, body, lbl, sub):
        w.bind("<Button-1>", lambda e, fn=command: fn())
        w.bind("<Return>", lambda e, fn=command: fn())
    return card


def _open(parent, module_name, class_name=None, function_name=None):
    try:
        mod = __import__(module_name, fromlist=["*"])
        if function_name:
            return getattr(mod, function_name)(parent)
        return getattr(mod, class_name)(parent)
    except Exception as exc:
        messagebox.showerror("Could not open", str(exc), parent=parent)


def install(app_cls):
    original_init = app_cls.__init__

    def __init__(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._dashboard_frame = None
        self._build_home_dashboard()
        self.show_dashboard()

    app_cls.__init__ = __init__

    def show_dashboard(self):
        if self._dashboard_frame is None:
            self._build_home_dashboard()
        try:
            self.pos_screen.pack_forget()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in dashboard.py", exc_info=exc)
        self._dashboard_frame.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)
        self._refresh_dashboard_metrics()
        self.focus_force()

    def show_pos_screen(self):
        try:
            self._dashboard_frame.pack_forget()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in dashboard.py", exc_info=exc)
        self.pos_screen.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.focus_force()
        try:
            self.code_entry.focus_set()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in dashboard.py", exc_info=exc)

    def _build_home_dashboard(self):
        frame = tk.Frame(self, bg="#f5f7fa")
        self._dashboard_frame = frame

        # ---------- Premium top bar ----------
        top = tk.Frame(frame, bg=PALETTE["nav"], height=70)
        top.pack(fill="x")
        top.pack_propagate(False)

        brand = tk.Frame(top, bg=PALETTE["nav"])
        brand.pack(side="left", padx=26)
        tk.Label(brand, text="BKPOS", font=("Segoe UI", 20, "bold"),
                 bg=PALETTE["nav"], fg="white").pack(anchor="w")
        tk.Label(brand, text="POINT OF SALE  /  CONTROL CENTRE",
                 font=("Segoe UI", 7, "bold"), bg=PALETTE["nav"], fg=PALETTE["nav_muted"]).pack(anchor="w")

        right = tk.Frame(top, bg=PALETTE["nav"])
        right.pack(side="right", padx=24)
        tk.Label(right, text=f"{self.cashier_name}  •  {self.cashier_role}",
                 font=("Segoe UI", 9, "bold"), bg=PALETTE["nav"], fg="white").pack(anchor="e")
        self._dash_date = tk.Label(right, text="", font=("Segoe UI", 8),
                                   bg=PALETTE["nav"], fg=PALETTE["nav_muted"])
        self._dash_date.pack(anchor="e", pady=(4,0))

        # ---------- Body ----------
        body = tk.Frame(frame, bg="#f5f7fa")
        body.pack(fill="both", expand=True, padx=24, pady=20)

        # Hero panel
        hero = tk.Frame(body, bg="#ffffff", bd=1, relief=tk.SOLID)
        hero.pack(fill="x", pady=(0,16))

        hleft = tk.Frame(hero, bg="#ffffff", padx=22, pady=18)
        hleft.pack(side="left", fill="both", expand=True)
        tk.Label(hleft, text="Good business starts here.",
                 font=("Segoe UI", 21, "bold"), bg="#ffffff", fg="#111827").pack(anchor="w")
        tk.Label(hleft, text="Start a sale, manage customer accounts, or jump straight into your daily controls.",
                 font=("Segoe UI", 9), bg="#ffffff", fg="#64748b").pack(anchor="w", pady=(6,0))

        action = tk.Frame(hero, bg="#ffffff", padx=20, pady=17)
        action.pack(side="right")
        tk.Button(action, text="＋  NEW SALE",
                  command=self.show_pos_screen, font=("Segoe UI", 11, "bold"),
                  bg="#0f7a3d", fg="white", activebackground="#0b6332",
                  activeforeground="white", bd=0, padx=25, pady=12,
                  cursor="hand2").pack()
        tk.Label(action, text="Ctrl+N  /  F12 payment",
                 font=("Segoe UI", 8), bg="#ffffff", fg="#94a3b8").pack(pady=(5,0))

        # ---------- KPI strip ----------
        stats = tk.Frame(body, bg="#f5f7fa")
        stats.pack(fill="x", pady=(0,16))
        self._kpi_labels = []

        cards = [
            ("💰 TODAY'S SALES", "—", "Revenue processed today", "#059669"),
            ("🧾 TRANSACTIONS", "—", "Completed sales tickets", "#2563eb"),
            ("👥 DEBTORS", "—", "Outstanding customer accounts", "#d97706"),
            ("📦 LOW STOCK", "—", "Items needing reorder", "#dc2626"),
        ]
        for i, (title, value, sub, col) in enumerate(cards):
            card = tk.Frame(stats, bg="#ffffff", bd=1, relief=tk.SOLID,
                            padx=17, pady=13, cursor="hand2")
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i==0 else 7, 0 if i==3 else 7))
            stats.grid_columnconfigure(i, weight=1)
            tk.Label(card, text=title, font=("Segoe UI", 9, "bold"),
                     bg="#ffffff", fg="#64748b", cursor="hand2").pack(anchor="w")
            val=tk.Label(card,text=value,font=("Segoe UI",19,"bold"),
                         bg="#ffffff",fg=col, cursor="hand2")
            val.pack(anchor="w", pady=(5,1))
            self._kpi_labels.append(val)
            tk.Label(card,text=sub,font=("Segoe UI",8),
                     bg="#ffffff",fg="#94a3b8", cursor="hand2").pack(anchor="w")
            # Clicking KPI card opens real-time analytics
            card.bind("<Button-1>", lambda e: _open(self, "ai.dashboard_charts", "AnalyticsChartsWindow"))
            for child in card.winfo_children():
                child.bind("<Button-1>", lambda e: _open(self, "ai.dashboard_charts", "AnalyticsChartsWindow"))

        # ---------- Main content ----------
        content = tk.Frame(body, bg="#f5f7fa")
        content.pack(fill="both", expand=True)

        left = tk.Frame(content, bg="#ffffff", bd=1, relief=tk.SOLID, padx=18, pady=16)
        left.pack(side="left", fill="both", expand=True, padx=(0,8))

        tk.Label(left, text="QUICK ACCESS", font=("Segoe UI", 9, "bold"),
                 bg="#ffffff", fg="#334155").pack(anchor="w")
        tk.Label(left, text="Your most-used tools",
                 font=("Segoe UI", 8), bg="#ffffff", fg="#94a3b8").pack(anchor="w", pady=(3,12))

        quick = tk.Frame(left, bg="#ffffff")
        quick.pack(fill="both", expand=True)
        for c in range(2): quick.grid_columnconfigure(c, weight=1)
        for r in range(4): quick.grid_rowconfigure(r, weight=1)

        items = [
            ("New Sale", "Open the sales screen", self.show_pos_screen, "#059669"),
            ("Open Invoices", "Resume an open invoice", self.open_invoice_selector, "#2563eb"),
            ("🤖 AI Copilot (F10)", "Natural language questions",
             lambda: _open(self, "ai.copilot", "AICopilotWindow"), "#6366f1"),
            ("🍎 Produce Vision (F4)", "Camera produce & scale scan",
             lambda: _open(self, "ai.vision_checkout", "ProduceVisionCheckoutWindow"), "#10b981"),
            ("Quotation", "Create or manage quotations",
             lambda: _open(self, "quotation", function_name="open_quotation"), "#7c3aed"),
            ("Customer & Pricing", "Customers and price levels",
             lambda: _open(self, "customer_pricing", function_name="open_customer_pricing"), "#0891b2"),
            ("Debtors", "Balances and account payments",
             lambda: _open(self, "customer_accounts", "CustomerAccountsWindow"), "#d97706"),
            ("Stock & Products", "Lookup and stock tools",
             lambda: _open(self, "professional_lookup", "PriceLookupWindow"), "#475569"),
        ]

        for idx,(title,sub,cmd,accent) in enumerate(items):
            r,c=divmod(idx,2)
            card=tk.Frame(quick,bg="#f8fafc",bd=1,relief=tk.SOLID,cursor="hand2")
            card.grid(row=r,column=c,sticky="nsew",padx=5,pady=5)
            bar=tk.Frame(card,bg=accent,width=4)
            bar.pack(side="left",fill="y")
            b=tk.Frame(card,bg="#f8fafc",padx=12,pady=10)
            b.pack(fill="both",expand=True)
            tk.Label(b,text=title,font=("Segoe UI",10,"bold"),
                     bg="#f8fafc",fg="#1e293b").pack(anchor="w")
            tk.Label(b,text=sub,font=("Segoe UI",8),
                     bg="#f8fafc",fg="#64748b").pack(anchor="w",pady=(3,0))
            for w in (card,bar,b):
                w.bind("<Button-1>",lambda e,fn=cmd:fn())

        rightpanel=tk.Frame(content,bg="#ffffff",bd=1,relief=tk.SOLID,padx=18,pady=16,width=275)
        rightpanel.pack(side="right",fill="y",padx=(8,0))
        rightpanel.pack_propagate(False)

        tk.Label(rightpanel,text="MANAGEMENT",font=("Segoe UI",9,"bold"),
                 bg="#ffffff",fg="#334155").pack(anchor="w")
        tk.Label(rightpanel,text="Back-office controls",font=("Segoe UI",8),
                 bg="#ffffff",fg="#94a3b8").pack(anchor="w",pady=(3,13))

        management=[
            ("AI Intelligence Suite","Copilot, OCR, Vision & Forecast",
             lambda:_open(self,"ai.ai_hub","AISuiteWindow")),
            ("Visual Analytics","Interactive sales & margin charts",
             lambda:_open(self,"ai.dashboard_charts","AnalyticsChartsWindow")),
            ("AI Upsell Engine","Basket cross-sell recommendations",
             lambda:_open(self,"ai.recommendations","UpsellManagementWindow")),
            ("Creditors","Supplier accounts",
             lambda:_open(self,"creditor_accounts","SupplierAccountsWindow")),
            ("Reports","Sales & control reports",
             lambda:_open(self,"professional_menu_cleanup","ReportsCentreWindow")),
            ("Utility & Admin","Shifts, audit & settings",
             lambda:_open(self,"smart_pos_controls","SmartManagementDashboard")),
        ]
        for title,sub,cmd in management:
            btn=tk.Frame(rightpanel,bg="#f8fafc",bd=1,relief=tk.SOLID,cursor="hand2")
            btn.pack(fill="x",pady=5)
            inner=tk.Frame(btn,bg="#f8fafc",padx=12,pady=10)
            inner.pack(fill="x")
            tk.Label(inner,text=title,font=("Segoe UI",9,"bold"),
                     bg="#f8fafc",fg="#1e293b").pack(anchor="w")
            tk.Label(inner,text=sub,font=("Segoe UI",8),
                     bg="#f8fafc",fg="#64748b").pack(anchor="w",pady=(2,0))
            for w in (btn,inner):
                w.bind("<Button-1>",lambda e,fn=cmd:fn())

        tk.Button(rightpanel,text="LOG OUT",command=self.log_out,
                  font=("Segoe UI",8,"bold"),bg="#eef2f5",fg="#475569",
                  bd=0,padx=15,pady=8,cursor="hand2").pack(side="bottom",anchor="e")

        footer=tk.Frame(frame,bg="#f5f7fa",height=30)
        footer.pack(fill="x",padx=24)
        tk.Label(footer,text="F1 Home   •   F3 Lookup   •   F4 Vision Scan   •   F9 Quotation   •   F10 Copilot   •   Ctrl+N New Invoice   •   F12 Payment",
                 font=("Segoe UI",8),bg="#f5f7fa",fg="#94a3b8").pack(anchor="w")

        self.bind("<Home>", lambda e:self.show_dashboard())
        self.bind("<F1>", lambda e:self.show_dashboard())

    def _refresh_dashboard_metrics(self):
        try:
            from datetime import datetime
            self._dash_date.config(text=datetime.now().strftime("%A, %d %B %Y  •  %H:%M"))
            sales, count, debtors, low = _db_metrics()
            self._kpi_labels[0].config(text=_money(sales))
            self._kpi_labels[1].config(text=str(count))
            self._kpi_labels[2].config(text=_money(debtors))
            self._kpi_labels[3].config(text=str(low))
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in dashboard.py", exc_info=exc)

    app_cls.show_dashboard = show_dashboard
    app_cls.show_pos_screen = show_pos_screen
    app_cls._build_home_dashboard = _build_home_dashboard
    app_cls._refresh_dashboard_metrics = _refresh_dashboard_metrics
    return app_cls
