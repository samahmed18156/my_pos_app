"""Professional Dashboard Enhancement for BKPOS.

This creates a highly professional, modern dashboard with:
- Modern color scheme with gradients
- Enhanced card designs with shadows
- Better typography and spacing
- Professional KPI visualization
- Improved layout and visual hierarchy
- Touch-friendly interactions
"""
from core.logger import logger as _bkpos_logger

import sqlite3
import tkinter as tk
from tkinter import messagebox
from datetime import datetime

from core.config import DB_PATH
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
            _bkpos_logger.warning("Suppressed exception in professional_dashboard.py", exc_info=exc)
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



def _analytics_metrics():
    """Return advanced management insights not shown by the existing KPI cards."""
    c = sqlite3.connect(DB_NAME)
    c.row_factory = sqlite3.Row
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        # Gross profit is calculated from the existing sales total and recorded item costs.
        row = c.execute(
            """SELECT COALESCE(SUM(s.total_amount),0) revenue,
                      COALESCE(SUM(s.total_cost),0) cost,
                      COALESCE(SUM(s.cash_amount),0) cash,
                      COALESCE(SUM(s.card_amount),0) card
                 FROM sales_history s
                WHERE date(s.timestamp)=date(?)
                  AND COALESCE(s.voided,0)=0""", (today,)
        ).fetchone()
        revenue = float(row["revenue"] or 0)
        cost = float(row["cost"] or 0)
        profit = revenue - cost
        margin = (profit / revenue * 100.0) if revenue else 0.0
        cash = float(row["cash"] or 0)
        card = float(row["card"] or 0)

        top = []
        if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sale_items'").fetchone():
            top = c.execute(
                """SELECT COALESCE(si.description, si.barcode, 'Unknown') name,
                          COALESCE(SUM(si.qty),0) qty,
                          COALESCE(SUM(si.value),0) value
                     FROM sale_items si
                     JOIN sales_history s ON s.id=si.sale_id
                    WHERE date(s.timestamp)=date(?) AND COALESCE(s.voided,0)=0
                    GROUP BY si.barcode, si.description
                    ORDER BY qty DESC, value DESC LIMIT 5""", (today,)
            ).fetchall()

        # Hourly revenue gives management a useful sales-activity pattern without
        # duplicating the existing sales-history report.
        hourly = c.execute(
            """SELECT CAST(strftime('%H', timestamp) AS INTEGER) hour,
                      COALESCE(SUM(total_amount),0) value
                 FROM sales_history
                WHERE date(timestamp)=date(?) AND COALESCE(voided,0)=0
                GROUP BY CAST(strftime('%H', timestamp) AS INTEGER)
                ORDER BY hour""", (today,)
        ).fetchall()
        return {
            "profit": profit, "margin": margin, "cash": cash, "card": card,
            "top": top, "hourly": hourly,
        }
    except sqlite3.Error as exc:
        _bkpos_logger.warning("Advanced dashboard metrics unavailable", exc_info=exc)
        return {"profit": 0.0, "margin": 0.0, "cash": 0.0, "card": 0.0, "top": [], "hourly": []}
    finally:
        c.close()

def _open(parent, module_name, class_name=None, function_name=None):
    try:
        mod = __import__(module_name, fromlist=["*"])
        if function_name:
            return getattr(mod, function_name)(parent)
        return getattr(mod, class_name)(parent)
    except Exception as exc:
        messagebox.showerror("Could not open", str(exc), parent=parent)



class BusinessIntelligenceWindow(tk.Toplevel):
    """Dedicated management analytics window for the new BI dashboard."""
    def __init__(self, parent):
        super().__init__(parent)
        self.title("BKPOS — Business Intelligence")
        self.geometry("1100x700")
        self.minsize(900, 600)
        self.configure(bg="#10233f")
        self.transient(parent)
        self._build()
        self.refresh()

    def _build(self):
        header=tk.Frame(self,bg="#18365f",padx=24,pady=18); header.pack(fill="x")
        tk.Label(header,text="BUSINESS INTELLIGENCE",font=("Segoe UI",18,"bold"),bg="#18365f",fg="white").pack(anchor="w")
        tk.Label(header,text="Advanced management insights from existing BKPOS transactions",font=("Segoe UI",9),bg="#18365f",fg="#b8c7d9").pack(anchor="w",pady=(4,0))
        body=tk.Frame(self,bg="#10233f",padx=24,pady=20); body.pack(fill="both",expand=True)
        cards=tk.Frame(body,bg="#10233f"); cards.pack(fill="x")
        self.labels=[]
        for title in ("PROFIT TODAY","MARGIN TODAY","CASH TODAY","CARD TODAY"):
            f=tk.Frame(cards,bg="#18365f",padx=18,pady=16); f.pack(side="left",fill="both",expand=True,padx=5)
            tk.Label(f,text=title,font=("Segoe UI",9,"bold"),bg="#18365f",fg="#b8c7d9").pack(anchor="w")
            l=tk.Label(f,text="R 0.00",font=("Segoe UI",20,"bold"),bg="#18365f",fg="white"); l.pack(anchor="w",pady=(7,0)); self.labels.append(l)
        lower=tk.Frame(body,bg="#10233f"); lower.pack(fill="both",expand=True,pady=(18,0))
        left=tk.Frame(lower,bg="#18365f",padx=18,pady=14); left.pack(side="left",fill="both",expand=True,padx=(0,6))
        tk.Label(left,text="TOP PRODUCTS TODAY",font=("Segoe UI",10,"bold"),bg="#18365f",fg="#b8c7d9").pack(anchor="w")
        self.top=tk.Text(left,bg="#18365f",fg="white",bd=0,highlightthickness=0,font=("Segoe UI",10),height=10); self.top.pack(fill="both",expand=True,pady=(8,0)); self.top.configure(state="disabled")
        right=tk.Frame(lower,bg="#18365f",padx=18,pady=14); right.pack(side="right",fill="both",expand=True,padx=(6,0))
        tk.Label(right,text="TODAY'S SALES ACTIVITY BY HOUR",font=("Segoe UI",10,"bold"),bg="#18365f",fg="#b8c7d9").pack(anchor="w")
        self.trend=tk.Canvas(right,bg="#18365f",highlightthickness=0,height=240); self.trend.pack(fill="both",expand=True,pady=(8,0))
        tk.Button(body,text="REFRESH",command=self.refresh,font=("Segoe UI",9,"bold"),bg="#eef2f7",fg="#334155",bd=0,padx=18,pady=8).pack(anchor="e",pady=(12,0))

    def refresh(self):
        m=_analytics_metrics()
        self.labels[0].config(text=_money(m["profit"]))
        self.labels[1].config(text=f'{m["margin"]:.1f}%')
        self.labels[2].config(text=_money(m["cash"]))
        self.labels[3].config(text=_money(m["card"]))
        self.top.configure(state="normal"); self.top.delete("1.0","end")
        if m["top"]:
            for i,r in enumerate(m["top"],1): self.top.insert("end",f'{i}. {r["name"]}  —  {int(r["qty"] or 0)} units  —  {_money(r["value"])}\n')
        else: self.top.insert("end","No sales recorded today.")
        self.top.configure(state="disabled")
        self.trend.delete("all")
        rows=m["hourly"]; vals=[float(r["value"] or 0) for r in rows]; mx=max(vals) if vals else 0
        w=max(self.trend.winfo_width(),500); h=220
        if rows:
            bw=max(8,(w-20)/max(len(rows),1)-4)
            for i,r in enumerate(rows):
                x=10+i*(bw+4); bh=(float(r["value"] or 0)/mx*180) if mx else 0
                self.trend.create_rectangle(x,h-bh,x+bw,h,fill="#10b981",outline="")
                self.trend.create_text(x+bw/2,h+8,text=f'{int(r["hour"]):02d}',fill="#b8c7d9",font=("Segoe UI",8))
        else:
            self.trend.create_text(w/2,h/2,text="No sales activity today",fill="#b8c7d9",font=("Segoe UI",10))

def install_professional_dashboard(app_cls):
    """Install the professional dashboard enhancement."""
    
    original_init = app_cls.__init__

    def __init__(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._professional_dashboard_frame = None
        self._build_professional_dashboard()
        self.show_professional_dashboard()

    app_cls.__init__ = __init__

    def show_professional_dashboard(self):
        if self._professional_dashboard_frame is None:
            self._build_professional_dashboard()
        try:
            self.pos_screen.pack_forget()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in professional_dashboard.py", exc_info=exc)
        self._professional_dashboard_frame.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        self._refresh_professional_metrics()
        self._refresh_business_intelligence()
        self.focus_force()

    def show_pos_screen(self):
        try:
            self._professional_dashboard_frame.pack_forget()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in professional_dashboard.py", exc_info=exc)
        self.pos_screen.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.focus_force()
        try:
            self.code_entry.focus_set()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in professional_dashboard.py", exc_info=exc)

    def _build_professional_dashboard(self):
        frame = tk.Frame(self, bg="#10233f")
        self._professional_dashboard_frame = frame

        # ---------- Modern Gradient Header ----------
        header = tk.Frame(frame, bg="#18365f", height=100)
        header.pack(fill="x")
        header.pack_propagate(False)

        # Gradient effect with multiple frames
        gradient1 = tk.Frame(header, bg="#10233f", height=100)
        gradient1.pack(side="left", fill="y")
        
        gradient2 = tk.Frame(header, bg="#18365f", height=100)
        gradient2.pack(side="left", fill="y", expand=True)

        # Brand section
        brand_frame = tk.Frame(gradient2, bg="#18365f")
        brand_frame.pack(side="left", padx=30, pady=20)
        
        tk.Label(brand_frame, text="BKPOS", font=("Segoe UI", 26, "bold"),
                 bg="#18365f", fg="#ffffff").pack(anchor="w")
        tk.Label(brand_frame, text="PROFESSIONAL POINT OF SALE SYSTEM",
                 font=("Segoe UI", 10, "bold"), bg="#18365f", fg="#b8c7d9").pack(anchor="w", pady=(5,0))
        try:
            from store_settings import get_store_name
            store_name = get_store_name()
        except Exception:
            store_name = "Family Supermarket"
        
        tk.Label(brand_frame, text=f"BKPOS 10.0.0  •  {store_name}",
                 font=("Segoe UI", 8), bg="#18365f", fg="#8fa5bf").pack(anchor="w", pady=(3,0))

        # User info section
        user_frame = tk.Frame(gradient2, bg="#18365f")
        user_frame.pack(side="right", padx=30, pady=20)
        
        tk.Label(user_frame, text=f"{self.cashier_name}", font=("Segoe UI", 14, "bold"),
                 bg="#18365f", fg="#ffffff").pack(anchor="e")
        tk.Label(user_frame, text=f"{self.cashier_role}", font=("Segoe UI", 10),
                 bg="#18365f", fg="#b8c7d9").pack(anchor="e", pady=(3,0))
        self._prof_date = tk.Label(user_frame, text="", font=("Segoe UI", 9),
                                  bg="#18365f", fg="#8fa5bf")
        self._prof_date.pack(anchor="e", pady=(3,0))

        # ---------- Main Content Area ----------
        main_content = tk.Frame(frame, bg="#10233f")
        main_content.pack(fill="both", expand=True)

        # ---------- Professional KPI Cards ----------
        kpi_section = tk.Frame(main_content, bg="#10233f", padx=30, pady=25)
        kpi_section.pack(fill="x")

        tk.Label(kpi_section, text="TODAY'S PERFORMANCE", font=("Segoe UI", 12, "bold"),
                 bg="#10233f", fg="#b8c7d9").pack(anchor="w", pady=(0, 15))

        kpi_container = tk.Frame(kpi_section, bg="#10233f")
        kpi_container.pack(fill="x")

        self._prof_kpi_labels = []

        kpi_data = [
            ("SALES REVENUE", "Total sales today", "#10b981", "💰"),
            ("TRANSACTIONS", "Completed sales", "#3b82f6", "🛒"),
            ("OUTSTANDING", "Customer debtors", "#f59e0b", "👥"),
            ("LOW STOCK", "Items need attention", "#ef4444", "⚠️"),
        ]

        for i, (title, subtitle, color, icon) in enumerate(kpi_data):
            kpi_card = tk.Frame(kpi_container, bg="#18365f", bd=0, relief=tk.FLAT,
                              padx=20, pady=20, cursor="hand2")
            kpi_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0 if i==0 else 10, 0 if i==3 else 10))
            
            # Card header
            card_header = tk.Frame(kpi_card, bg="#18365f")
            card_header.pack(fill="x", pady=(0, 10))
            
            tk.Label(card_header, text=icon, font=("Segoe UI", 16), bg="#18365f", fg=color).pack(side="left")
            tk.Label(card_header, text=title, font=("Segoe UI", 9, "bold"),
                     bg="#18365f", fg="#b8c7d9").pack(side="right")
            
            # Value
            value_label = tk.Label(kpi_card, text="—", font=("Segoe UI", 24, "bold"),
                                 bg="#18365f", fg="#ffffff")
            value_label.pack(anchor="w", pady=(5, 8))
            self._prof_kpi_labels.append(value_label)
            
            # Subtitle
            tk.Label(kpi_card, text=subtitle, font=("Segoe UI", 8),
                     bg="#18365f", fg="#8fa5bf").pack(anchor="w")

        # ---------- Advanced Business Intelligence ----------
        analytics_section = tk.Frame(main_content, bg="#10233f", padx=30, pady=(0, 12))
        analytics_section.pack(fill="x")
        tk.Label(analytics_section, text="BUSINESS INTELLIGENCE", font=("Segoe UI", 12, "bold"),
                 bg="#10233f", fg="#b8c7d9").pack(anchor="w", pady=(0, 10))

        insight_row = tk.Frame(analytics_section, bg="#10233f")
        insight_row.pack(fill="x")
        for i in range(3): insight_row.grid_columnconfigure(i, weight=1)

        # Profitability panel
        profit_panel = tk.Frame(insight_row, bg="#18365f", padx=18, pady=14)
        profit_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        tk.Label(profit_panel, text="PROFITABILITY TODAY", font=("Segoe UI", 9, "bold"),
                 bg="#18365f", fg="#b8c7d9").pack(anchor="w")
        self._bi_profit = tk.Label(profit_panel, text="R 0.00", font=("Segoe UI", 20, "bold"),
                                   bg="#18365f", fg="#ffffff")
        self._bi_profit.pack(anchor="w", pady=(6, 0))
        self._bi_margin = tk.Label(profit_panel, text="Margin: 0.0%", font=("Segoe UI", 9),
                                   bg="#18365f", fg="#8fa5bf")
        self._bi_margin.pack(anchor="w", pady=(2, 0))

        # Payment mix panel
        mix_panel = tk.Frame(insight_row, bg="#18365f", padx=18, pady=14)
        mix_panel.grid(row=0, column=1, sticky="nsew", padx=6)
        tk.Label(mix_panel, text="PAYMENT MIX TODAY", font=("Segoe UI", 9, "bold"),
                 bg="#18365f", fg="#b8c7d9").pack(anchor="w")
        self._bi_cash = tk.Label(mix_panel, text="Cash  R 0.00", font=("Segoe UI", 11, "bold"),
                                 bg="#18365f", fg="#ffffff")
        self._bi_cash.pack(anchor="w", pady=(7, 0))
        self._bi_card = tk.Label(mix_panel, text="Card  R 0.00", font=("Segoe UI", 11, "bold"),
                                 bg="#18365f", fg="#ffffff")
        self._bi_card.pack(anchor="w", pady=(3, 0))

        # Top products panel
        top_panel = tk.Frame(insight_row, bg="#18365f", padx=18, pady=14)
        top_panel.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        tk.Label(top_panel, text="TOP PRODUCTS TODAY", font=("Segoe UI", 9, "bold"),
                 bg="#18365f", fg="#b8c7d9").pack(anchor="w")
        self._bi_top = tk.Label(top_panel, text="No sales yet", font=("Segoe UI", 9),
                                bg="#18365f", fg="#ffffff", justify="left", anchor="w")
        self._bi_top.pack(anchor="w", pady=(6, 0), fill="x")

        # Hourly activity strip: a compact visual trend, not a replacement for Reports.
        trend_panel = tk.Frame(analytics_section, bg="#18365f", padx=18, pady=12)
        trend_panel.pack(fill="x", pady=(8, 0))
        tk.Label(trend_panel, text="TODAY'S SALES ACTIVITY BY HOUR", font=("Segoe UI", 9, "bold"),
                 bg="#18365f", fg="#b8c7d9").pack(anchor="w")
        self._bi_trend = tk.Canvas(trend_panel, height=58, bg="#18365f", highlightthickness=0)
        self._bi_trend.pack(fill="x", pady=(7, 0))

        # ---------- Quick Actions Section ----------
        actions_section = tk.Frame(main_content, bg="#10233f", padx=30, pady=(25, 25))
        actions_section.pack(fill="both", expand=True)

        tk.Label(actions_section, text="QUICK ACTIONS", font=("Segoe UI", 12, "bold"),
                 bg="#10233f", fg="#b8c7d9").pack(anchor="w", pady=(0, 15))

        actions_container = tk.Frame(actions_section, bg="#10233f")
        actions_container.pack(fill="both", expand=True)

        # Primary actions
        primary_actions = tk.Frame(actions_container, bg="#10233f")
        primary_actions.pack(fill="x", pady=(0, 20))

        # New Sale button - prominent
        new_sale_btn = tk.Button(
            primary_actions,
            text="🛒 START NEW SALE",
            command=self.show_pos_screen,
            font=("Segoe UI", 14, "bold"),
            bg="#10b981",
            fg="white",
            activebackground="#059669",
            activeforeground="white",
            relief=tk.FLAT,
            bd=0,
            padx=30,
            pady=15,
            cursor="hand2"
        )
        new_sale_btn.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # Secondary actions grid
        secondary_frame = tk.Frame(actions_container, bg="#10233f")
        secondary_frame.pack(fill="both", expand=True)

        secondary_actions = [
            ("📋 OPEN INVOICES", self.open_invoice_selector, "#3b82f6"),
            ("📝 QUOTATIONS", lambda: _open(self, "quotation", function_name="open_quotation"), "#8b5cf6"),
            ("👥 CUSTOMERS", lambda: _open(self, "customer_pricing", function_name="open_customer_pricing"), "#06b6d4"),
            ("💰 DEBTORS", lambda: _open(self, "customer_accounts", "CustomerAccountsWindow"), "#f59e0b"),
            ("📦 STOCK", lambda: _open(self, "professional_lookup", "PriceLookupWindow"), "#64748b"),
            ("📊 REPORTS", lambda: _open(self, "professional_menu_cleanup", "ReportsCentreWindow"), "#ec4899"),
        ]

        for i, (text, command, color) in enumerate(secondary_actions):
            row, col = divmod(i, 3)
            action_btn = tk.Button(
                secondary_frame,
                text=text,
                command=command,
                font=("Segoe UI", 11, "bold"),
                bg="#18365f",
                fg=color,
                activebackground="#244a78",
                activeforeground=color,
                relief=tk.FLAT,
                bd=0,
                padx=15,
                pady=12,
                cursor="hand2"
            )
            action_btn.grid(row=row, column=col, sticky="nsew", padx=5, pady=5)

        for i in range(3):
            secondary_frame.grid_columnconfigure(i, weight=1)
        for i in range(2):
            secondary_frame.grid_rowconfigure(i, weight=1)

        # ---------- Management Section ----------
        management_section = tk.Frame(actions_container, bg="#18365f", bd=1, relief=tk.FLAT, padx=20, pady=15)
        management_section.pack(fill="x", pady=(20, 0))

        tk.Label(management_section, text="⚙️ MANAGEMENT", font=("Segoe UI", 10, "bold"),
                 bg="#18365f", fg="#b8c7d9").pack(anchor="w", pady=(0, 10))

        management_buttons = tk.Frame(management_section, bg="#18365f")
        management_buttons.pack(fill="x")

        mgmt_actions = [
            ("🏢 CREDITORS", lambda: _open(self, "creditor_accounts", "SupplierAccountsWindow")),
            ("🔧 UTILITY", lambda: _open(self, "smart_pos_controls", "SmartManagementDashboard")),
            ("🚪 LOG OUT", self.log_out),
        ]

        for text, command in mgmt_actions:
            btn = tk.Button(
                management_buttons,
                text=text,
                command=command,
                font=("Segoe UI", 9, "bold"),
                bg="#10233f",
                fg="#ffffff",
                activebackground="#244a78",
                relief=tk.FLAT,
                bd=0,
                padx=12,
                pady=8,
                cursor="hand2"
            )
            btn.pack(side=tk.LEFT, padx=5)

        # ---------- Footer ----------
        footer = tk.Frame(frame, bg="#10233f", height=40)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        tk.Label(footer, text="F1 Home  •  F3 Product Lookup  •  F9 Quotation  •  Ctrl+N New Sale  •  Ctrl+I Open Invoices  •  F12 Payment",
                 font=("Segoe UI", 8), bg="#10233f", fg="#6f88a5").pack(anchor="center", pady=10)

        # Keyboard bindings
        self.bind("<Home>", lambda e: self.show_professional_dashboard())
        self.bind("<F1>", lambda e: self.show_professional_dashboard())

    def _refresh_professional_metrics(self):
        try:
            self._prof_date.config(text=datetime.now().strftime("%A, %d %B %Y  •  %H:%M"))
            sales, count, debtors, low = _db_metrics()
            self._prof_kpi_labels[0].config(text=_money(sales))
            self._prof_kpi_labels[1].config(text=str(count))
            self._prof_kpi_labels[2].config(text=_money(debtors))
            self._prof_kpi_labels[3].config(text=str(low))
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in professional_dashboard.py", exc_info=exc)


    def _refresh_business_intelligence(self):
        try:
            m = _analytics_metrics()
            self._bi_profit.config(text=_money(m["profit"]))
            self._bi_margin.config(text=f"Margin: {m['margin']:.1f}%")
            self._bi_cash.config(text=f"Cash  {_money(m['cash'])}")
            self._bi_card.config(text=f"Card  {_money(m['card'])}")
            if m["top"]:
                lines = []
                for idx, r in enumerate(m["top"], 1):
                    name = str(r["name"] or "Unknown")[:28]
                    lines.append(f"{idx}. {name}  •  {float(r['qty'] or 0):g} units")
                self._bi_top.config(text="\n".join(lines))
            else:
                self._bi_top.config(text="No sales yet")

            self._bi_trend.delete("all")
            hourly = [(int(r["hour"]), float(r["value"] or 0)) for r in m["hourly"]]
            max_value = max([v for _, v in hourly] or [1.0])
            width = max(self._bi_trend.winfo_width(), 500)
            left, right, base = 8, width - 8, 45
            slot = max((right - left) / 12.0, 25)
            for h, value in hourly:
                x = left + (h - 8) * slot
                if x < left or x > right:
                    continue
                bar_h = max(3, 32 * value / max_value)
                self._bi_trend.create_rectangle(x, base - bar_h, x + max(8, slot - 6), base, fill="#3b82f6", outline="")
                self._bi_trend.create_text(x + 4, 54, text=f"{h:02d}", anchor="w", fill="#8fa5bf", font=("Segoe UI", 7))
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in business intelligence refresh", exc_info=exc)

    app_cls.show_professional_dashboard = show_professional_dashboard
    app_cls.show_pos_screen = show_pos_screen
    app_cls._build_professional_dashboard = _build_professional_dashboard
    app_cls._refresh_professional_metrics = _refresh_professional_metrics
    
    return app_cls


if __name__ == "__main__":
    print("Professional Dashboard Enhancement for BKPOS")
    print("This module provides a modern, professional dashboard interface.")