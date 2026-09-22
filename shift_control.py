"""Phase 11: cashier shift and workforce control analytics.

Read-only management controls built on the existing cashier_shifts and sales
history records. No existing posting, checkout, stock, or accounting workflow
is changed.
"""
import csv
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

from core.config import DB_PATH


def _table_exists(conn, name):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None


def shift_summary(conn, start_date, end_date):
    """Return shift-level operational performance for the inclusive date range."""
    if not _table_exists(conn, "cashier_shifts"):
        return []
    rows = conn.execute("""
        SELECT cs.id, cs.cashier, cs.opened_at, cs.closed_at, cs.status,
               COALESCE(cs.opening_cash,0), COALESCE(cs.closing_cash,0),
               COALESCE(cs.expected_cash,0), COALESCE(cs.difference,0),
               COALESCE(SUM(CASE WHEN COALESCE(s.voided,0)=0 AND COALESCE(s.status,'COMPLETED')='COMPLETED'
                                 THEN s.total_amount ELSE 0 END),0) AS sales,
               COUNT(CASE WHEN COALESCE(s.voided,0)=0 AND COALESCE(s.status,'COMPLETED')='COMPLETED' THEN s.id END) AS transactions
        FROM cashier_shifts cs
        LEFT JOIN sales_history s ON s.cashier=cs.cashier
          AND datetime(s.timestamp) >= datetime(cs.opened_at)
          AND datetime(s.timestamp) <= datetime(COALESCE(cs.closed_at,datetime('now','localtime')))
        WHERE date(cs.opened_at) BETWEEN ? AND ?
        GROUP BY cs.id
        ORDER BY cs.id DESC
    """, (start_date, end_date)).fetchall()
    return [tuple(r) for r in rows]


def cashier_performance(conn, start_date, end_date):
    """Aggregate completed sales, transactions, voids and returns by cashier."""
    sales = conn.execute("""
        SELECT COALESCE(s.cashier,'Unknown'), COALESCE(SUM(s.total_amount),0), COUNT(*)
        FROM sales_history s
        WHERE date(s.timestamp) BETWEEN ? AND ?
          AND COALESCE(s.voided,0)=0 AND COALESCE(s.status,'COMPLETED')='COMPLETED'
        GROUP BY COALESCE(s.cashier,'Unknown')
    """, (start_date, end_date)).fetchall()
    voids = {}
    for cashier, count in conn.execute("""
        SELECT COALESCE(cashier,'Unknown'), COUNT(*) FROM sales_history
        WHERE date(timestamp) BETWEEN ? AND ? AND COALESCE(voided,0)=1 GROUP BY COALESCE(cashier,'Unknown')
    """, (start_date, end_date)).fetchall():
        voids[cashier] = count
    returns = {}
    if _table_exists(conn, "return_history"):
        for cashier, amount in conn.execute("""
            SELECT COALESCE(cashier,'Unknown'), COALESCE(SUM(total_amount),0) FROM return_history
            WHERE date(timestamp) BETWEEN ? AND ? GROUP BY COALESCE(cashier,'Unknown')
        """, (start_date, end_date)).fetchall():
            returns[cashier] = float(amount or 0)
    result = []
    for cashier, total, transactions in sales:
        result.append((cashier, float(total or 0), int(transactions or 0),
                       float(total or 0) / int(transactions or 1), int(voids.get(cashier, 0)), returns.get(cashier, 0.0)))
    return sorted(result, key=lambda x: x[1], reverse=True)


def shift_exceptions(conn, start_date, end_date, tolerance=0.01):
    """Return open shifts and cash variances requiring management attention."""
    rows = shift_summary(conn, start_date, end_date)
    result = []
    for r in rows:
        if r[4] == 'OPEN':
            result.append((r[0], r[1], 'Open shift', 'Shift has not been closed'))
        elif abs(float(r[8] or 0)) > tolerance:
            result.append((r[0], r[1], 'Cash variance', f"Variance R {float(r[8]):,.2f}"))
    return result


class ShiftControlWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("Shift & Cashier Control Center")
        self.geometry("1180x760")
        self.configure(bg="#eef2f7")
        self.transient(parent)
        self.grab_set()
        self.build()
        self.refresh()

    def build(self):
        tk.Label(self, text="SHIFT & CASHIER CONTROL CENTER", font=("Arial", 19, "bold"), bg="#2c5282", fg="white", pady=12).pack(fill="x")
        top = tk.Frame(self, bg="#eef2f7", pady=10)
        top.pack(fill="x", padx=20)
        tk.Label(top, text="From (YYYY-MM-DD):", bg="#eef2f7", font=("Arial", 10, "bold")).pack(side="left")
        self.start = tk.Entry(top, width=12); self.start.pack(side="left", padx=6)
        tk.Label(top, text="To:", bg="#eef2f7", font=("Arial", 10, "bold")).pack(side="left")
        self.end = tk.Entry(top, width=12); self.end.pack(side="left", padx=6)
        today = datetime.now().strftime("%Y-%m-%d")
        self.start.insert(0, today); self.end.insert(0, today)
        tk.Button(top, text="REFRESH", command=self.refresh, font=("Arial", 10, "bold")).pack(side="left", padx=10)
        tk.Button(top, text="EXPORT CSV", command=self.export_csv, font=("Arial", 10, "bold")).pack(side="right")

        self.alert = tk.Label(self, text="", anchor="w", justify="left", bg="white", font=("Arial", 11, "bold"), padx=15, pady=10)
        self.alert.pack(fill="x", padx=20, pady=(0, 10))

        self.tabs = ttk.Notebook(self); self.tabs.pack(fill="both", expand=True, padx=20, pady=10)
        self.shift_tab = tk.Frame(self.tabs, bg="white"); self.cashier_tab = tk.Frame(self.tabs, bg="white")
        self.tabs.add(self.shift_tab, text="Shift Performance"); self.tabs.add(self.cashier_tab, text="Cashier Performance")
        self.shift_tree = self._tree(self.shift_tab, [("id","Shift",70),("cashier","Cashier",130),("opened","Opened",145),("closed","Closed",145),("status","Status",90),("sales","Sales",120),("tx","Transactions",100),("variance","Variance",110)])
        self.cashier_tree = self._tree(self.cashier_tab, [("cashier","Cashier",150),("sales","Sales",140),("tx","Transactions",110),("avg","Avg Basket",120),("voids","Voids",80),("returns","Returns",120)])

    def _tree(self, parent, columns):
        tree = ttk.Treeview(parent, columns=[c[0] for c in columns], show="headings")
        for key, heading, width in columns:
            tree.heading(key, text=heading); tree.column(key, width=width, anchor="e" if key in {"sales","avg","variance","returns","tx","voids"} else "w")
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        return tree

    def _dates(self):
        a, b = self.start.get().strip(), self.end.get().strip()
        datetime.strptime(a, "%Y-%m-%d"); datetime.strptime(b, "%Y-%m-%d")
        if a > b: raise ValueError("From date cannot be after To date")
        return a, b

    def refresh(self):
        try: a, b = self._dates()
        except Exception as e:
            messagebox.showerror("Invalid dates", str(e), parent=self); return
        c = sqlite3.connect(DB_PATH)
        shifts = shift_summary(c, a, b); cashiers = cashier_performance(c, a, b); exceptions = shift_exceptions(c, a, b); c.close()
        for x in self.shift_tree.get_children(): self.shift_tree.delete(x)
        for r in shifts:
            self.shift_tree.insert("", "end", values=(r[0],r[1],r[2],r[3] or "—",r[4],f"R {r[9]:,.2f}",r[10],f"R {r[8]:,.2f}"))
        for x in self.cashier_tree.get_children(): self.cashier_tree.delete(x)
        for r in cashiers:
            self.cashier_tree.insert("", "end", values=(r[0],f"R {r[1]:,.2f}",r[2],f"R {r[3]:,.2f}",r[4],f"R {r[5]:,.2f}"))
        if exceptions:
            self.alert.config(text=f"ATTENTION: {len(exceptions)} shift exception(s) require review.")
        else:
            self.alert.config(text="● ALL CLEAR — No open-shift or cash-variance exceptions in the selected period.")

    def export_csv(self):
        try: a, b = self._dates()
        except Exception as e:
            messagebox.showerror("Invalid dates", str(e), parent=self); return
        path = filedialog.asksaveasfilename(parent=self, title="Export shift control", defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path: return
        c = sqlite3.connect(DB_PATH); shifts = shift_summary(c, a, b); cashiers = cashier_performance(c, a, b); c.close()
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f); w.writerow(["Shift Control Report", a, b]); w.writerow([])
            w.writerow(["Shift ID","Cashier","Opened","Closed","Status","Opening Cash","Closing Cash","Expected Cash","Variance","Sales","Transactions"])
            w.writerows(shifts); w.writerow([]); w.writerow(["Cashier","Sales","Transactions","Average Basket","Voids","Returns"]); w.writerows(cashiers)
        messagebox.showinfo("Export complete", f"Saved to:\n{path}", parent=self)
