import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox

from core.config import DB_PATH
from ui.window_polish import polish_window
DB_NAME = DB_PATH
VAT_RATE = 0.15


def ensure_return_tables():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS return_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            original_sale_id INTEGER NOT NULL,
            total_amount REAL NOT NULL DEFAULT 0,
            refund_type TEXT NOT NULL,
            cashier TEXT DEFAULT 'Unknown',
            reason TEXT DEFAULT ''
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS return_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            return_id INTEGER NOT NULL,
            sale_item_id INTEGER NOT NULL,
            barcode TEXT,
            description TEXT,
            qty REAL NOT NULL,
            price REAL NOT NULL,
            value REAL NOT NULL
        )
    """)
    conn.commit()
    conn.close()


class ReturnsWindow(tk.Toplevel):
    """Find completed sales and process full or partial returns safely."""

    def __init__(self, parent):
        super().__init__(parent)
        polish_window(self)
        self.parent = parent
        self.cashier = getattr(parent, "cashier_username", None) or getattr(parent, "cashier_name", "") or "Unknown"
        self.title("Returns & Refunds")
        self.geometry("1120x720")
        self.minsize(980, 620)
        self.configure(bg="#eef2f7")
        self.transient(parent)
        self.grab_set()

        ensure_return_tables()
        self.sale_id = None
        self.items = []
        self.build_ui()
        self.load_sales()

    def build_ui(self):
        bg = "#eef2f7"
        card = "#ffffff"
        blue = "#2c5282"
        green = "#38a169"

        header = tk.Frame(self, bg=blue, padx=18, pady=14)
        header.pack(fill=tk.X)
        tk.Label(header, text="RETURNS & REFUNDS", font=("Arial", 18, "bold"),
                 bg=blue, fg="white").pack(side=tk.LEFT)
        tk.Label(header, text="Find a completed sale and return selected items",
                 font=("Arial", 11), bg=blue, fg="white").pack(side=tk.RIGHT)

        search = tk.Frame(self, bg=bg, padx=14, pady=10)
        search.pack(fill=tk.X)
        tk.Label(search, text="Search Sale #:", font=("Arial", 12, "bold"), bg=bg).pack(side=tk.LEFT)
        self.search_entry = tk.Entry(search, font=("Arial", 13), width=18)
        self.search_entry.pack(side=tk.LEFT, padx=8)
        self.search_entry.bind("<Return>", lambda e: self.load_sales())
        tk.Button(search, text="SEARCH", font=("Arial", 11, "bold"), bg=blue, fg="white",
                  padx=14, pady=6, command=self.load_sales).pack(side=tk.LEFT, padx=4)
        tk.Button(search, text="SHOW RECENT", font=("Arial", 11, "bold"), bg="#718096", fg="white",
                  padx=14, pady=6, command=self.show_recent).pack(side=tk.LEFT, padx=4)

        body = tk.Frame(self, bg=bg, padx=14)
        body.pack(fill=tk.BOTH, expand=True)

        left = tk.LabelFrame(body, text="Completed Sales", font=("Arial", 12, "bold"),
                             bg=card, padx=8, pady=8)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 7))

        cols = ("id", "date", "total", "payment", "cashier")
        self.sales_tree = ttk.Treeview(left, columns=cols, show="headings", height=16)
        headings = {"id": "Sale #", "date": "Date & Time", "total": "Total", "payment": "Payment", "cashier": "Cashier"}
        widths = {"id": 80, "date": 175, "total": 110, "payment": 125, "cashier": 125}
        for c in cols:
            self.sales_tree.heading(c, text=headings[c])
            self.sales_tree.column(c, width=widths[c], anchor="center")
        sb1 = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self.sales_tree.yview)
        self.sales_tree.configure(yscrollcommand=sb1.set)
        sb1.pack(side=tk.RIGHT, fill=tk.Y)
        self.sales_tree.pack(fill=tk.BOTH, expand=True)
        self.sales_tree.bind("<<TreeviewSelect>>", self.on_sale_selected)

        right = tk.LabelFrame(body, text="Items in Selected Sale", font=("Arial", 12, "bold"),
                              bg=card, padx=8, pady=8)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(7, 0))

        item_cols = ("item_id", "code", "description", "sold", "returned", "remaining", "price", "return_qty", "value")
        self.items_tree = ttk.Treeview(right, columns=item_cols, show="headings", height=16)
        item_heads = {
            "item_id": "ID", "code": "Code", "description": "Description", "sold": "Sold",
            "returned": "Returned", "remaining": "Remaining", "price": "Price", "return_qty": "Return Qty", "value": "Value"
        }
        item_widths = {"item_id": 45, "code": 95, "description": 190, "sold": 55, "returned": 70,
                       "remaining": 80, "price": 80, "return_qty": 90, "value": 90}
        for c in item_cols:
            self.items_tree.heading(c, text=item_heads[c])
            self.items_tree.column(c, width=item_widths[c], anchor="center")
        sb2 = ttk.Scrollbar(right, orient=tk.VERTICAL, command=self.items_tree.yview)
        self.items_tree.configure(yscrollcommand=sb2.set)
        sb2.pack(side=tk.RIGHT, fill=tk.Y)
        self.items_tree.pack(fill=tk.BOTH, expand=True)
        self.items_tree.bind("<Double-1>", self.edit_return_qty)

        hint = tk.Label(right, text="Double-click Return Qty to edit it. 0 = no return.",
                        font=("Arial", 10), bg=card, fg="#718096")
        hint.pack(anchor="w", pady=(7, 0))

        bottom = tk.Frame(self, bg=bg, padx=14, pady=10)
        bottom.pack(fill=tk.X)

        info = tk.Frame(bottom, bg=card, bd=1, relief=tk.SOLID, padx=12, pady=8)
        info.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.total_label = tk.Label(info, text="Return Total: R 0.00", font=("Arial", 16, "bold"),
                                    bg=card, fg=blue)
        self.total_label.pack(side=tk.LEFT)
        self.vat_label = tk.Label(info, text="VAT Included: R 0.00", font=("Arial", 11, "bold"),
                                  bg=card, fg="#4a5568")
        self.vat_label.pack(side=tk.LEFT, padx=25)

        actions = tk.Frame(bottom, bg=bg)
        actions.pack(side=tk.RIGHT, padx=(10, 0))
        tk.Button(actions, text="CANCEL / CLOSE", font=("Arial", 11, "bold"),
                  bg="#718096", fg="white", padx=16, pady=9, command=self.destroy).pack(side=tk.LEFT, padx=4)
        self.process_btn = tk.Button(actions, text="PROCESS RETURN", font=("Arial", 11, "bold"),
                                     bg=green, fg="white", padx=18, pady=9, command=self.process_return)
        self.process_btn.pack(side=tk.LEFT, padx=4)

        self.bind("<Escape>", lambda e: self.destroy())

    def show_recent(self):
        self.search_entry.delete(0, tk.END)
        self.load_sales()

    def load_sales(self):
        ensure_return_tables()
        for iid in self.sales_tree.get_children():
            self.sales_tree.delete(iid)
        term = self.search_entry.get().strip()
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        if term.isdigit():
            cur.execute("""
                SELECT id, timestamp, total_amount, payment_type, cashier
                FROM sales_history WHERE id = ? ORDER BY id DESC
            """, (int(term),))
        else:
            cur.execute("""
                SELECT id, timestamp, total_amount, payment_type, cashier
                FROM sales_history ORDER BY id DESC LIMIT 100
            """)
        rows = cur.fetchall()
        conn.close()
        for row in rows:
            sid, stamp, total, payment, cashier = row
            self.sales_tree.insert("", tk.END, iid=str(sid), values=(
                f"#{sid}", str(stamp or "")[:16], f"R {float(total or 0):,.2f}",
                payment or "Unknown", cashier or "Unknown"
            ))

    def on_sale_selected(self, event=None):
        selected = self.sales_tree.selection()
        if not selected:
            return
        self.sale_id = int(selected[0])
        self.load_sale_items()

    def load_sale_items(self):
        for iid in self.items_tree.get_children():
            self.items_tree.delete(iid)
        self.items = []
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        cur.execute("""
            SELECT si.id, si.barcode, si.description, si.qty, si.price, si.value,
                   COALESCE((SELECT SUM(ri.qty) FROM return_items ri WHERE ri.sale_item_id = si.id), 0)
            FROM sale_items si
            WHERE si.sale_id = ? ORDER BY si.id
        """, (self.sale_id,))
        rows = cur.fetchall()
        conn.close()
        for item_id, code, desc, sold, price, value, returned in rows:
            sold = float(sold or 0)
            returned = float(returned or 0)
            remaining = max(0.0, sold - returned)
            self.items.append({"id": item_id, "code": code, "description": desc, "sold": sold,
                               "returned": returned, "remaining": remaining, "price": float(price or 0)})
            self.items_tree.insert("", tk.END, iid=str(item_id), values=(
                item_id, code or "", desc or "", self.fmt_qty(sold), self.fmt_qty(returned),
                self.fmt_qty(remaining), f"R {float(price or 0):.2f}", "0", "R 0.00"
            ))
        self.update_total()

    @staticmethod
    def fmt_qty(q):
        return str(int(q)) if float(q).is_integer() else f"{q:.3f}".rstrip("0").rstrip(".")

    def edit_return_qty(self, event=None):
        item = self.items_tree.identify_row(event.y) if event else self.items_tree.focus()
        if not item:
            return
        col = self.items_tree.identify_column(event.x) if event else "#8"
        if col not in ("#8",):
            return
        current = self.items_tree.set(item, "return_qty")
        popup = tk.Toplevel(self)
        popup.title("Return Quantity")
        popup.geometry("320x170")
        popup.resizable(False, False)
        popup.transient(self)
        popup.grab_set()
        tk.Label(popup, text="Quantity to return", font=("Arial", 13, "bold")).pack(pady=(20, 8))
        entry = tk.Entry(popup, font=("Arial", 15), justify="center")
        entry.pack(padx=30, fill=tk.X)
        entry.insert(0, current or "0")
        entry.select_range(0, tk.END)

        def save():
            try:
                qty = float(entry.get().strip())
                if qty < 0:
                    raise ValueError
                data = next(x for x in self.items if str(x["id"]) == str(item))
                if qty > data["remaining"] + 1e-9:
                    raise ValueError("over")
            except ValueError as exc:
                messagebox.showerror("Invalid Quantity", "Return quantity cannot exceed the remaining quantity.", parent=popup)
                return
            self.items_tree.set(item, "return_qty", self.fmt_qty(qty))
            self.items_tree.set(item, "value", f"R {qty * data['price']:.2f}")
            popup.destroy()
            self.update_total()

        tk.Button(popup, text="SAVE", font=("Arial", 11, "bold"), bg="#38a169", fg="white", padx=20, pady=6, command=save).pack(pady=12)
        entry.bind("<Return>", lambda e: save())
        popup.bind("<Escape>", lambda e: popup.destroy())
        entry.focus_set()

    def get_selected_return_lines(self):
        result = []
        for iid in self.items_tree.get_children():
            try:
                qty = float(self.items_tree.set(iid, "return_qty") or 0)
            except ValueError:
                qty = 0
            if qty <= 0:
                continue
            data = next(x for x in self.items if str(x["id"]) == str(iid))
            if qty > data["remaining"] + 1e-9:
                raise ValueError(f"Return quantity for {data['description']} exceeds the remaining quantity.")
            result.append({**data, "qty": qty, "value": qty * data["price"]})
        return result

    def update_total(self):
        total = 0.0
        for iid in self.items_tree.get_children():
            try:
                qty = float(self.items_tree.set(iid, "return_qty") or 0)
            except ValueError:
                qty = 0
            try:
                price = next(x["price"] for x in self.items if str(x["id"]) == str(iid))
            except StopIteration:
                price = 0
            value = qty * price
            self.items_tree.set(iid, "value", f"R {value:.2f}")
            total += value
        vat = total * VAT_RATE / (1 + VAT_RATE)
        self.total_label.config(text=f"Return Total: R {total:,.2f}")
        self.vat_label.config(text=f"VAT Included: R {vat:,.2f}")

    def process_return(self):
        if not self.sale_id:
            messagebox.showwarning("Select Sale", "Please select a completed sale first.", parent=self)
            return
        try:
            lines = self.get_selected_return_lines()
        except ValueError as exc:
            messagebox.showerror("Invalid Return", str(exc), parent=self)
            return
        if not lines:
            messagebox.showwarning("No Items", "Enter a return quantity for at least one item.", parent=self)
            return
        total = sum(x["value"] for x in lines)

        choice = tk.StringVar(value="Cash Refund")
        reason = tk.StringVar()
        dialog = tk.Toplevel(self)
        dialog.title("Confirm Return")
        dialog.geometry("460x360")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()
        tk.Label(dialog, text="CONFIRM RETURN", font=("Arial", 16, "bold")).pack(pady=(20, 8))
        tk.Label(dialog, text=f"Original Sale: #{self.sale_id}\nReturn Total: R {total:,.2f}", font=("Arial", 12, "bold")).pack(pady=5)
        tk.Label(dialog, text="Refund method", font=("Arial", 11, "bold")).pack(anchor="w", padx=30, pady=(15, 5))
        for value in ("Cash Refund", "Credit Note"):
            tk.Radiobutton(dialog, text=value, variable=choice, value=value, font=("Arial", 11)).pack(anchor="w", padx=45)
        tk.Label(dialog, text="Reason (optional)", font=("Arial", 11, "bold")).pack(anchor="w", padx=30, pady=(12, 4))
        tk.Entry(dialog, textvariable=reason, font=("Arial", 11), width=42).pack(padx=30)

        def confirm():
            conn = sqlite3.connect(DB_NAME)
            try:
                from services.returns_service import post_return
                lines_for_service = [
                    {"sale_item_id": line["id"], "qty": line["qty"]}
                    for line in lines
                ]
                return_id, posted_total = post_return(
                    conn, sale_id=self.sale_id, lines=lines_for_service,
                    refund_type=choice.get(),
                    cashier=getattr(self.parent, "cashier_username", "Unknown"),
                    reason=reason.get().strip(),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

            dialog.destroy()
            messagebox.showinfo(
                "Return Completed",
                f"Return #{return_id} completed successfully.\n\n"
                f"Original sale: #{self.sale_id}\n"
                f"Return total: R {total:,.2f}\n"
                f"Refund: {choice.get()}\n"
                "Stock has been restored.",
                parent=self
            )
            self.load_sale_items()
            self.update_total()

        tk.Button(dialog, text="CANCEL", font=("Arial", 11, "bold"), bg="#718096", fg="white", padx=16, pady=7, command=dialog.destroy).pack(side=tk.LEFT, padx=(90, 8), pady=20)
        tk.Button(dialog, text="CONFIRM RETURN", font=("Arial", 11, "bold"), bg="#38a169", fg="white", padx=16, pady=7, command=confirm).pack(side=tk.LEFT, padx=8, pady=20)
        dialog.bind("<Escape>", lambda e: dialog.destroy())
