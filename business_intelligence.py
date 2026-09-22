"""BKPOS Business Intelligence dashboard.

Read-only analytics built on existing sales, sale_items, products and branch data.
No posting, stock, accounting or pricing logic is changed here.
"""
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

from core.config import DB_PATH


def _conn():
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.execute("PRAGMA foreign_keys=ON")
    return c


def _date_ok(value):
    datetime.strptime(value, "%Y-%m-%d")
    return value


def _money(value):
    return f"R {float(value or 0):,.2f}"


class BusinessIntelligenceWindow(tk.Toplevel):
    """Management dashboard for sales, margin, products, cashiers and branches."""

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("BKPOS Business Intelligence")
        self.geometry("1280x820")
        self.minsize(1100, 700)
        self.configure(bg="#eef2f7")
        self.transient(parent)
        self.grab_set()
        self._build()
        self._set_period(30)
        self.refresh()

    def _build(self):
        tk.Label(self, text="BUSINESS INTELLIGENCE", font=("Segoe UI", 20, "bold"),
                 bg="#2c5282", fg="white", pady=14).pack(fill="x")
        bar = tk.Frame(self, bg="#eef2f7", pady=10)
        bar.pack(fill="x", padx=15)
        tk.Label(bar, text="From", bg="#eef2f7", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.frm = tk.Entry(bar, width=12)
        self.frm.pack(side="left", padx=5)
        tk.Label(bar, text="To", bg="#eef2f7", font=("Segoe UI", 10, "bold")).pack(side="left")
        self.to = tk.Entry(bar, width=12)
        self.to.pack(side="left", padx=5)
        for days, label in [(1, "Today"), (7, "7 Days"), (30, "30 Days"), (90, "90 Days")]:
            tk.Button(bar, text=label, command=lambda d=days: self._set_period(d)).pack(side="left", padx=3)
        tk.Button(bar, text="RUN ANALYTICS", command=self.refresh,
                  font=("Segoe UI", 10, "bold")).pack(side="left", padx=8)
        self.status = tk.Label(bar, text="", bg="#eef2f7", anchor="w")
        self.status.pack(side="left", padx=10)

        cards = tk.Frame(self, bg="#eef2f7")
        cards.pack(fill="x", padx=15, pady=5)
        self.card_labels = {}
        for i, key in enumerate(["Sales", "Profit", "Margin", "Transactions", "Avg Basket", "Units"]):
            f = tk.Frame(cards, bg="white", bd=1, relief="solid")
            f.grid(row=0, column=i, padx=4, sticky="nsew")
            cards.grid_columnconfigure(i, weight=1)
            tk.Label(f, text=key, bg="white", font=("Segoe UI", 9, "bold")).pack(pady=(9, 2))
            value = tk.Label(f, text="—", bg="white", font=("Segoe UI", 15, "bold"))
            value.pack(pady=(0, 10))
            self.card_labels[key] = value

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=15, pady=10)
        self.trend_tab = tk.Frame(notebook, bg="white")
        self.products_tab = tk.Frame(notebook, bg="white")
        self.people_tab = tk.Frame(notebook, bg="white")
        self.branches_tab = tk.Frame(notebook, bg="white")
        self.stock_tab = tk.Frame(notebook, bg="white")
        notebook.add(self.trend_tab, text="Sales Trend")
        notebook.add(self.products_tab, text="Products & Categories")
        notebook.add(self.people_tab, text="Cashiers")
        notebook.add(self.branches_tab, text="Branches")
        notebook.add(self.stock_tab, text="Stock Intelligence")
        self._build_trend()
        self._build_tables()

    def _set_period(self, days):
        end = datetime.now().date()
        start = end - timedelta(days=days - 1)
        self.frm.delete(0, "end"); self.frm.insert(0, start.isoformat())
        self.to.delete(0, "end"); self.to.insert(0, end.isoformat())

    def _build_trend(self):
        self.canvas = tk.Canvas(self.trend_tab, bg="white", highlightthickness=0, height=360)
        self.canvas.pack(fill="both", expand=True, padx=15, pady=15)
        self.trend_summary = tk.Label(self.trend_tab, text="", bg="white", anchor="w",
                                      font=("Segoe UI", 10, "bold"))
        self.trend_summary.pack(fill="x", padx=15, pady=(0, 10))

    def _make_tree(self, parent, columns, headings, widths):
        frame = tk.Frame(parent, bg="white")
        frame.pack(fill="both", expand=True, padx=12, pady=12)
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        for col, heading, width in zip(columns, headings, widths):
            tree.heading(col, text=heading)
            tree.column(col, width=width, anchor="e" if col not in (columns[0],) else "w")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        return tree

    def _build_tables(self):
        self.product_tree = self._make_tree(self.products_tab,
            ("product", "category", "units", "sales", "profit", "margin"),
            ("Product", "Category", "Units", "Sales", "Profit", "Margin"),
            (260, 150, 90, 140, 140, 100))
        self.cashier_tree = self._make_tree(self.people_tab,
            ("cashier", "transactions", "sales", "profit", "avg"),
            ("Cashier", "Transactions", "Sales", "Profit", "Avg Basket"),
            (220, 130, 150, 150, 130))
        self.branch_tree = self._make_tree(self.branches_tab,
            ("branch", "transactions", "sales", "profit", "margin"),
            ("Branch", "Transactions", "Sales", "Profit", "Margin"),
            (260, 130, 160, 160, 120))
        self.stock_tree = self._make_tree(self.stock_tab,
            ("product", "barcode", "stock", "minimum", "status"),
            ("Product", "Barcode", "On Hand", "Minimum", "Status"),
            (300, 180, 120, 120, 160))

    def _clear(self, tree):
        tree.delete(*tree.get_children())

    def refresh(self):
        try:
            start, end = _date_ok(self.frm.get().strip()), _date_ok(self.to.get().strip())
            if start > end:
                raise ValueError("From date cannot be after To date")
            c = _conn()
            try:
                self._refresh_kpis(c, start, end)
                self._refresh_trend(c, start, end)
                self._refresh_products(c, start, end)
                self._refresh_cashiers(c, start, end)
                self._refresh_branches(c, start, end)
                self._refresh_stock(c)
            finally:
                c.close()
            self.status.config(text=f"Analytics: {start} to {end}")
        except Exception as exc:
            messagebox.showerror("Business Intelligence", f"Could not load analytics:\n{exc}", parent=self)

    def _sales_filter(self):
        return "date(s.timestamp) BETWEEN ? AND ? AND COALESCE(s.voided,0)=0 AND COALESCE(s.status,'COMPLETED')='COMPLETED'"

    def _refresh_kpis(self, c, start, end):
        row = c.execute(f"""SELECT COALESCE(SUM(s.total_amount),0),
                                  COALESCE(SUM(s.total_cost),0), COUNT(*),
                                  COALESCE(SUM(si.qty),0)
                           FROM sales_history s
                           LEFT JOIN sale_items si ON si.sale_id=s.id
                           WHERE {self._sales_filter()}""", (start, end)).fetchone()
        sales, cost, transactions, units = map(float, row or (0, 0, 0, 0))
        # Avoid multiplying header totals by item count: recalculate transaction KPIs separately.
        header = c.execute(f"SELECT COALESCE(SUM(total_amount),0),COALESCE(SUM(total_cost),0),COUNT(*) FROM sales_history s WHERE {self._sales_filter()}", (start, end)).fetchone()
        sales, cost, transactions = map(float, header)
        units = float(c.execute(f"SELECT COALESCE(SUM(si.qty),0) FROM sale_items si JOIN sales_history s ON s.id=si.sale_id WHERE {self._sales_filter()}", (start, end)).fetchone()[0] or 0)
        profit = sales - cost
        margin = (profit / sales * 100) if sales else 0
        self.card_labels["Sales"].config(text=_money(sales))
        self.card_labels["Profit"].config(text=_money(profit))
        self.card_labels["Margin"].config(text=f"{margin:.1f}%")
        self.card_labels["Transactions"].config(text=f"{int(transactions):,}")
        self.card_labels["Avg Basket"].config(text=_money(sales / transactions if transactions else 0))
        self.card_labels["Units"].config(text=f"{units:,.0f}")

    def _refresh_trend(self, c, start, end):
        rows = c.execute(f"""SELECT date(s.timestamp),COALESCE(SUM(s.total_amount),0)
                            FROM sales_history s WHERE {self._sales_filter()}
                            GROUP BY date(s.timestamp) ORDER BY date(s.timestamp)""", (start, end)).fetchall()
        self.canvas.delete("all")
        w = max(self.canvas.winfo_width(), 700); h = max(self.canvas.winfo_height(), 330)
        if not rows:
            self.canvas.create_text(w/2, h/2, text="No completed sales in this period.", font=("Segoe UI", 14))
            self.trend_summary.config(text="No sales data")
            return
        vals = [float(r[1] or 0) for r in rows]; maxv = max(vals) or 1
        left, right, top, bottom = 70, 25, 25, 55
        plot_w, plot_h = w-left-right, h-top-bottom
        n = len(rows); step = plot_w / max(n, 1)
        points = []
        for i, (day, value) in enumerate(rows):
            x = left + step * (i + 0.5)
            y = top + plot_h - (float(value)/maxv)*plot_h
            points.append((x, y))
            self.canvas.create_rectangle(x-step*0.35, y, x+step*0.35, top+plot_h, outline="")
            self.canvas.create_line(x, y, x, top+plot_h)
            if n <= 14 or i in (0, n-1):
                self.canvas.create_text(x, top+plot_h+20, text=day[5:], font=("Segoe UI", 8))
        for frac in (0, .25, .5, .75, 1):
            y = top + plot_h - frac*plot_h
            self.canvas.create_line(left, y, w-right, y, dash=(2, 4))
            self.canvas.create_text(left-8, y, text=_money(maxv*frac), anchor="e", font=("Segoe UI", 8))
        if len(points) > 1:
            self.canvas.create_line(*[p for xy in points for p in xy], width=2)
        total = sum(vals); avg = total / len(vals)
        best = max(rows, key=lambda r: float(r[1] or 0))
        self.trend_summary.config(text=f"Daily average: {_money(avg)}   |   Best day: {best[0]} ({_money(best[1])})   |   Total: {_money(total)}")

    def _refresh_products(self, c, start, end):
        self._clear(self.product_tree)
        rows = c.execute(f"""SELECT COALESCE(si.description,p.description,'Unknown'),
                            COALESCE(p.category,''), COALESCE(SUM(si.qty),0),
                            COALESCE(SUM(si.value),0),
                            COALESCE(SUM(si.qty*COALESCE(si.cost_price,0)),0)
                     FROM sale_items si JOIN sales_history s ON s.id=si.sale_id
                     LEFT JOIN products p ON p.barcode=si.barcode
                     WHERE {self._sales_filter()}
                     GROUP BY si.barcode,si.description,p.category
                     ORDER BY SUM(si.value) DESC LIMIT 25""", (start, end)).fetchall()
        for name, category, units, sales, cost in rows:
            profit = float(sales or 0)-float(cost or 0); margin = profit/float(sales)*100 if sales else 0
            self.product_tree.insert("", "end", values=(name, category, f"{float(units):g}", _money(sales), _money(profit), f"{margin:.1f}%"))

        # Add category rollups below product data is intentionally kept separate in the same tab title.
        # Product ranking remains the primary action-oriented view.

    def _refresh_cashiers(self, c, start, end):
        self._clear(self.cashier_tree)
        rows = c.execute(f"""SELECT COALESCE(s.cashier,'Unknown'),COUNT(*),
                            COALESCE(SUM(s.total_amount),0),COALESCE(SUM(s.total_amount-s.total_cost),0)
                     FROM sales_history s WHERE {self._sales_filter()}
                     GROUP BY COALESCE(s.cashier,'Unknown') ORDER BY SUM(s.total_amount) DESC""", (start, end)).fetchall()
        for cashier, transactions, sales, profit in rows:
            avg=float(sales or 0)/transactions if transactions else 0
            self.cashier_tree.insert("", "end", values=(cashier, transactions, _money(sales), _money(profit), _money(avg)))

    def _refresh_branches(self, c, start, end):
        self._clear(self.branch_tree)
        rows = c.execute(f"""SELECT COALESCE(s.branch_name,CAST(s.branch_id AS TEXT),'Main'),COUNT(*),
                            COALESCE(SUM(s.total_amount),0),COALESCE(SUM(s.total_amount-s.total_cost),0)
                     FROM sales_history s WHERE {self._sales_filter()}
                     GROUP BY COALESCE(s.branch_name,CAST(s.branch_id AS TEXT),'Main')
                     ORDER BY SUM(s.total_amount) DESC""", (start, end)).fetchall()
        for branch, transactions, sales, profit in rows:
            margin=float(profit or 0)/float(sales)*100 if sales else 0
            self.branch_tree.insert("", "end", values=(branch, transactions, _money(sales), _money(profit), f"{margin:.1f}%"))

    def _refresh_stock(self, c):
        self._clear(self.stock_tree)
        # Products table is already provisioned by the existing POS migrations.
        rows = c.execute("""SELECT description,barcode,COALESCE(stock_on_hand,0),COALESCE(min_stock,5)
                            FROM products
                            WHERE COALESCE(active,1)=1 AND COALESCE(stock_on_hand,0)<=COALESCE(min_stock,5)
                            ORDER BY stock_on_hand ASC, description ASC LIMIT 50""").fetchall()
        for name, barcode, stock, minimum in rows:
            status = "OUT OF STOCK" if float(stock or 0) <= 0 else "LOW STOCK"
            self.stock_tree.insert("", "end", values=(name, barcode, f"{float(stock or 0):g}", f"{float(minimum or 0):g}", status))


def open_business_intelligence(parent):
    return BusinessIntelligenceWindow(parent)
