from core.logger import logger as _bkpos_logger
from tkinter import messagebox
import os
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from creditor_payments import SupplierPaymentsWindow

from core.config import DB_PATH
from ui.window_polish import polish_window
DB_NAME = DB_PATH
BG = "#eef2f7"
NAVY = "#1f3f68"
BLUE = "#2b6cb0"
GREEN = "#2f855a"
RED = "#c53030"
WHITE = "white"


def conn():
    return sqlite3.connect(DB_NAME)


def ensure_supplier_schema():
    c = conn()
    try:
        cols = {r[1] for r in c.execute("PRAGMA table_info(accounts)").fetchall()}
        additions = {
            "supplier_account_no": "TEXT",
            "email": "TEXT",
            "contact_person": "TEXT",
            "registration_no": "TEXT",
            "vat_no": "TEXT",
            "payment_terms": "TEXT",
            "credit_limit": "REAL DEFAULT 0",
            "currency": "TEXT DEFAULT 'ZAR'",
            "active": "INTEGER DEFAULT 1",
            "notes": "TEXT",
            "created_at": "DATETIME DEFAULT CURRENT_TIMESTAMP",
        }
        for name, typ in additions.items():
            if name not in cols:
                c.execute(f"ALTER TABLE accounts ADD COLUMN {name} {typ}")

        # Give every existing supplier a controlled account number.
        suppliers = c.execute("SELECT id FROM accounts WHERE type='Supplier' ORDER BY id").fetchall()
        for (sid,) in suppliers:
            row = c.execute("SELECT supplier_account_no FROM accounts WHERE id=?", (sid,)).fetchone()
            if not row or not (row[0] or "").strip():
                c.execute("SELECT supplier_account_no FROM accounts WHERE supplier_account_no IS NOT NULL AND supplier_account_no<>''")
                used = {r[0] for r in c.fetchall()}
                n = 1
                while f"SUP-{n:06d}" in used:
                    n += 1
                c.execute("UPDATE accounts SET supplier_account_no=? WHERE id=?", (f"SUP-{n:06d}", sid))
        c.commit()
    finally:
        c.close()


def next_supplier_account(c):
    row = c.execute("SELECT supplier_account_no FROM accounts WHERE type='Supplier' AND supplier_account_no LIKE 'SUP-%' ORDER BY id DESC").fetchone()
    n = 1
    if row and row[0]:
        try:
            n = int(str(row[0]).split('-')[-1]) + 1
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in creditors.py", exc_info=exc)
    used = {r[0] for r in c.execute("SELECT supplier_account_no FROM accounts WHERE supplier_account_no IS NOT NULL").fetchall()}
    while f"SUP-{n:06d}" in used:
        n += 1
    return f"SUP-{n:06d}"


class SupplierMasterWindow(tk.Toplevel):
    """Single professional master screen for supplier/creditor maintenance."""
    def __init__(self, parent):
        super().__init__(parent)
        polish_window(self)
        self.parent = parent
        self.title("Supplier Master (Creditors)")
        self.geometry("1250x820")
        self.minsize(1050, 700)
        self.configure(bg=BG)
        self.transient(parent)
        ensure_supplier_schema()
        self.selected_id = None
        self.editing = False
        self.vars = {}
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.build()
        self.refresh()
        self.clear_form()
        self.after(100, lambda: self.search.focus_set())
        self.bind_all("<F2>", lambda e: self.new_supplier())
        self.bind_all("<F3>", lambda e: self.edit_supplier())
        self.bind_all("<F4>", lambda e: self.delete_supplier())
        self.bind_all("<F5>", lambda e: self.statement())
        self.bind_all("<F6>", lambda e: self.purchase_history())
        self.bind_all("<Escape>", lambda e: self.close())

    def build(self):
        header = tk.Frame(self, bg=NAVY, height=76)
        header.pack(fill="x")
        tk.Label(header, text="SUPPLIER MASTER (CREDITORS)", font=("Arial", 20, "bold"), bg=NAVY, fg=WHITE).pack(pady=(12, 2))
        tk.Label(header, text="Create and manage supplier accounts used by GRN and creditor records.", font=("Arial", 10), bg=NAVY, fg=WHITE).pack()

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=12)

        left = tk.Frame(body, bg=WHITE, bd=1, relief="solid", width=360)
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)
        tk.Label(left, text="SUPPLIER ACCOUNTS", font=("Arial", 13, "bold"), bg=WHITE, fg=NAVY).pack(fill="x", padx=12, pady=(12, 8))
        sf = tk.Frame(left, bg=WHITE)
        sf.pack(fill="x", padx=12)
        self.search_mode = ttk.Combobox(sf, values=["By Name", "By Account No.", "By Phone"], state="readonly", width=13)
        self.search_mode.set("By Name")
        self.search_mode.pack(side="left")
        self.search = tk.Entry(sf, font=("Arial", 11))
        self.search.pack(side="left", fill="x", expand=True, padx=(6, 0))
        self.search.bind("<KeyRelease>", lambda e: self.refresh())
        self.search.bind("<Down>", self.focus_supplier_list)

        treef = tk.Frame(left, bg=WHITE)
        treef.pack(fill="both", expand=True, padx=12, pady=10)
        self.acc_tree = ttk.Treeview(treef, columns=("account", "name"), show="headings", selectmode="browse")
        self.acc_tree.heading("account", text="Account No.")
        self.acc_tree.heading("name", text="Supplier Name")
        self.acc_tree.column("account", width=115, anchor="w")
        self.acc_tree.column("name", width=190, anchor="w")
        vs = ttk.Scrollbar(treef, orient="vertical", command=self.acc_tree.yview)
        self.acc_tree.configure(yscrollcommand=vs.set)
        self.acc_tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.acc_tree.bind("<<TreeviewSelect>>", self.on_select)
        self.acc_tree.bind("<Return>", lambda e: self.edit_supplier())
        self.acc_tree.bind("<F3>", lambda e: self.edit_supplier())

        btns = tk.Frame(left, bg=WHITE)
        btns.pack(fill="x", padx=12, pady=(0, 10))
        for text, cmd, bgc in [("+ ADD NEW\nF2", self.new_supplier, GREEN), ("EDIT\nF3", self.edit_supplier, BLUE), ("DELETE\nF4", self.delete_supplier, RED)]:
            tk.Button(btns, text=text, command=cmd, bg=bgc, fg=WHITE, font=("Arial", 10, "bold"), width=10, height=2).pack(side="left", padx=3, expand=True, fill="x")
        low = tk.Frame(left, bg=WHITE)
        low.pack(fill="x", padx=12, pady=(0, 12))
        tk.Button(low, text="SUPPLIER STATEMENT\nF5", command=self.statement, bg=WHITE, fg=NAVY, font=("Arial", 9, "bold"), relief="groove").pack(side="left", fill="x", expand=True, padx=3)
        tk.Button(low, text="PURCHASE HISTORY\nF6", command=self.purchase_history, bg=WHITE, fg=NAVY, font=("Arial", 9, "bold"), relief="groove").pack(side="left", fill="x", expand=True, padx=3)
        tk.Button(low, text="SUPPLIER PAYMENTS", command=self.open_payments, bg="#e6fffa", fg=NAVY, font=("Arial", 9, "bold"), relief="groove").pack(side="left", fill="x", expand=True, padx=3)
        self.count_label = tk.Label(left, text="", bg=WHITE, fg="#555", font=("Arial", 9))
        self.count_label.pack(pady=(0, 8))

        right = tk.Frame(body, bg=WHITE, bd=1, relief="solid")
        right.pack(side="left", fill="both", expand=True)
        tk.Label(right, text="SUPPLIER DETAILS", font=("Arial", 13, "bold"), bg=WHITE, fg=NAVY, anchor="w").pack(fill="x", padx=15, pady=(12, 6))

        form = tk.Frame(right, bg=WHITE)
        form.pack(fill="x", padx=15)
        self._field(form, "Supplier Account No.", "supplier_account_no", 0, 0, readonly=True)
        self._field(form, "Supplier Name *", "name", 0, 2)
        self._field(form, "Registration No.", "registration_no", 1, 0)
        self._field(form, "VAT No.", "vat_no", 1, 2)
        self._field(form, "Contact Person", "contact_person", 2, 0)
        self._field(form, "Phone", "phone", 2, 2)
        self._field(form, "Email", "email", 3, 0)
        self._field(form, "Payment Terms", "payment_terms", 3, 2, combo=["Cash", "7 Days", "14 Days", "30 Days", "60 Days", "90 Days"])
        self._field(form, "Credit Limit (R)", "credit_limit", 4, 0)
        self._field(form, "Currency", "currency", 4, 2, combo=["ZAR", "USD", "EUR", "GBP"])
        self._field(form, "Status", "active", 5, 0, combo=["Active", "Inactive"])
        tk.Label(form, text="Address", font=("Arial", 10, "bold"), bg=WHITE).grid(row=6, column=0, sticky="nw", padx=4, pady=7)
        self.vars["address"] = tk.Text(form, height=4, width=38, font=("Arial", 10))
        self.vars["address"].grid(row=6, column=1, columnspan=3, sticky="ew", padx=6, pady=7)
        tk.Label(form, text="Notes", font=("Arial", 10, "bold"), bg=WHITE).grid(row=7, column=0, sticky="nw", padx=4, pady=7)
        self.vars["notes"] = tk.Text(form, height=3, width=38, font=("Arial", 10))
        self.vars["notes"].grid(row=7, column=1, columnspan=3, sticky="ew", padx=6, pady=7)
        form.grid_columnconfigure(1, weight=1); form.grid_columnconfigure(3, weight=1)

        action = tk.Frame(right, bg=WHITE)
        action.pack(fill="x", padx=15, pady=8)
        self.save_btn = tk.Button(action, text="SAVE SUPPLIER", bg=GREEN, fg=WHITE, font=("Arial", 11, "bold"), command=self.save_supplier, width=20, height=2)
        self.save_btn.pack(side="left", padx=4)
        tk.Button(action, text="CLEAR / NEW", bg="#718096", fg=WHITE, font=("Arial", 11, "bold"), command=self.clear_form, width=16, height=2).pack(side="left", padx=4)
        tk.Button(action, text="CLOSE  ESC", bg=NAVY, fg=WHITE, font=("Arial", 11, "bold"), command=self.close, width=16, height=2).pack(side="right", padx=4)

        self.summary = tk.Label(right, text="Select a supplier to view purchase information.", bg="#f7fafc", fg="#333", font=("Arial", 11, "bold"), anchor="w", justify="left", padx=12, pady=10)
        self.summary.pack(fill="x", padx=15, pady=(4, 8))

        tk.Label(right, text="PURCHASE HISTORY", font=("Arial", 11, "bold"), bg=WHITE, fg=NAVY, anchor="w").pack(fill="x", padx=15)
        hist = tk.Frame(right, bg=WHITE)
        hist.pack(fill="both", expand=True, padx=15, pady=(4, 12))
        cols = ("date", "document", "invoice", "reference", "amount")
        self.txn_tree = ttk.Treeview(hist, columns=cols, show="headings")
        for col, title, width in [("date", "Date", 110), ("document", "Document No.", 120), ("invoice", "Supplier Invoice", 150), ("reference", "Reference", 130), ("amount", "Amount (R)", 120)]:
            self.txn_tree.heading(col, text=title); self.txn_tree.column(col, width=width, anchor="e" if col == "amount" else "w")
        sv = ttk.Scrollbar(hist, orient="vertical", command=self.txn_tree.yview); self.txn_tree.configure(yscrollcommand=sv.set)
        self.txn_tree.pack(side="left", fill="both", expand=True); sv.pack(side="right", fill="y")
        self.txn_tree.bind("<Double-1>", lambda e: self.purchase_history())

        tk.Label(self, text="F2 Add New    F3 Edit    F4 Delete    F5 Statement    F6 Purchase History    ESC Close", bg="#dbe8f5", fg=NAVY, font=("Arial", 10, "bold"), pady=7).pack(fill="x", side="bottom")

    def _field(self, parent, label, key, row, col, readonly=False, combo=None):
        tk.Label(parent, text=label, font=("Arial", 10, "bold"), bg=WHITE).grid(row=row, column=col, sticky="w", padx=4, pady=6)
        var = tk.StringVar()
        self.vars[key] = var
        if combo:
            w = ttk.Combobox(parent, textvariable=var, values=combo, state="readonly", font=("Arial", 10))
        else:
            w = tk.Entry(parent, textvariable=var, font=("Arial", 10), state="readonly" if readonly else "normal")
        w.grid(row=row, column=col+1, sticky="ew", padx=6, pady=6)
        return w

    def focus_supplier_list(self, event=None):
        if self.acc_tree.get_children():
            self.acc_tree.focus(self.acc_tree.get_children()[0]); self.acc_tree.selection_set(self.acc_tree.get_children()[0]); self.acc_tree.focus_set()
        return "break"

    def refresh(self, event=None):
        ensure_supplier_schema()
        q = self.search.get().strip()
        mode = self.search_mode.get()
        for x in self.acc_tree.get_children(): self.acc_tree.delete(x)
        c = conn()
        try:
            if mode == "By Account No.":
                rows = c.execute("SELECT id,supplier_account_no,name FROM accounts WHERE type='Supplier' AND supplier_account_no LIKE ? ORDER BY name COLLATE NOCASE", (f"%{q}%",)).fetchall()
            elif mode == "By Phone":
                rows = c.execute("SELECT id,supplier_account_no,name FROM accounts WHERE type='Supplier' AND phone LIKE ? ORDER BY name COLLATE NOCASE", (f"%{q}%",)).fetchall()
            else:
                rows = c.execute("SELECT id,supplier_account_no,name FROM accounts WHERE type='Supplier' AND name LIKE ? ORDER BY name COLLATE NOCASE", (f"%{q}%",)).fetchall()
            for sid, account, name in rows:
                self.acc_tree.insert("", "end", iid=str(sid), values=(account or "", name or ""))
            self.count_label.config(text=f"Total Suppliers: {len(rows)}")
        finally:
            c.close()

    def on_select(self, event=None):
        sel = self.acc_tree.selection()
        if not sel: return
        self.selected_id = int(sel[0]); self.editing = True
        self.load_supplier(self.selected_id)

    def load_supplier(self, sid):
        c = conn()
        try:
            r = c.execute("""SELECT supplier_account_no,name,registration_no,vat_no,contact_person,phone,email,address,
                            payment_terms,credit_limit,currency,active,notes FROM accounts WHERE id=? AND type='Supplier'""", (sid,)).fetchone()
            if not r: return
            keys = ["supplier_account_no","name","registration_no","vat_no","contact_person","phone","email","address","payment_terms","credit_limit","currency","active","notes"]
            for k, v in zip(keys, r):
                if k in ("address", "notes"):
                    self.vars[k].delete("1.0", "end"); self.vars[k].insert("1.0", v or "")
                elif k == "active": self.vars[k].set("Active" if int(v or 0) else "Inactive")
                else: self.vars[k].set("" if v is None else str(v))
            total = c.execute("SELECT COALESCE(SUM(total),0), COUNT(*) FROM grn_headers WHERE supplier_account=? OR supplier_name=?", (r[0], r[1])).fetchone()
            self.summary.config(text=f"Supplier: {r[1]}    |    Account: {r[0]}    |    Total GRNs: {total[1]}    |    Purchases: R {total[0]:,.2f}")
            for x in self.txn_tree.get_children(): self.txn_tree.delete(x)
            try:
                hist = c.execute("""SELECT created_at,grn_no,supplier_invoice,reference,total FROM grn_headers
                                   WHERE supplier_account=? OR supplier_name=? ORDER BY id DESC LIMIT 100""", (r[0], r[1])).fetchall()
                for h in hist:
                    self.txn_tree.insert("", "end", values=(h[0] or "", h[1] or "", h[2] or "", h[3] or "", f"R {float(h[4] or 0):,.2f}"))
            except sqlite3.OperationalError:
                _bkpos_logger.warning("Suppressed exception in creditors.py", exc_info=exc)
        finally:
            c.close()

    def clear_form(self):
        self.selected_id = None; self.editing = False
        c = conn()
        try: account = next_supplier_account(c)
        finally: c.close()
        for k, v in self.vars.items():
            if isinstance(v, tk.Text): v.delete("1.0", "end")
            else: v.set("")
        self.vars["supplier_account_no"].set(account)
        self.vars["payment_terms"].set("30 Days")
        self.vars["credit_limit"].set("0")
        self.vars["currency"].set("ZAR")
        self.vars["active"].set("Active")
        self.summary.config(text="New supplier — account number is generated by the system.")
        for x in self.txn_tree.get_children(): self.txn_tree.delete(x)
        self.save_btn.config(text="SAVE SUPPLIER")

    def new_supplier(self):
        self.clear_form()
        self.vars["name"].set("")
        self.after(50, lambda: self.vars["name"].trace_add("write", lambda *a: None) if False else None)
        return "break"

    def edit_supplier(self):
        sel = self.acc_tree.selection()
        if sel:
            self.selected_id = int(sel[0]); self.load_supplier(self.selected_id); self.editing = True
        elif self.selected_id:
            self.load_supplier(self.selected_id)
        else:
            messagebox.showinfo("Supplier Master", "Select a supplier to edit.", parent=self)
        return "break"

    def save_supplier(self):
        name = self.vars["name"].get().strip()
        if not name:
            messagebox.showerror("Supplier", "Supplier Name is required.", parent=self); return
        try: credit = float(self.vars["credit_limit"].get() or 0)
        except ValueError:
            messagebox.showerror("Supplier", "Credit Limit must be numeric.", parent=self); return
        c = conn()
        try:
            # Prevent accidental duplicate supplier names.
            dup = c.execute("SELECT id FROM accounts WHERE type='Supplier' AND lower(trim(name))=lower(trim(?)) AND id<>?", (name, self.selected_id or -1)).fetchone()
            if dup:
                messagebox.showwarning("Duplicate Supplier", "A supplier with this name already exists. Select that supplier instead of creating a duplicate.", parent=self); return
            vals = {k: (v.get("1.0", "end").strip() if isinstance(v, tk.Text) else v.get().strip()) for k,v in self.vars.items()}
            if self.selected_id:
                c.execute("""UPDATE accounts SET name=?,registration_no=?,vat_no=?,contact_person=?,phone=?,email=?,address=?,
                             payment_terms=?,credit_limit=?,currency=?,active=?,notes=? WHERE id=? AND type='Supplier'""",
                          (name, vals["registration_no"], vals["vat_no"], vals["contact_person"], vals["phone"], vals["email"], vals["address"], vals["payment_terms"], credit, vals["currency"], 1 if vals["active"]=="Active" else 0, vals["notes"], self.selected_id))
                action = "SUPPLIER_UPDATED"
                sid = self.selected_id
            else:
                account = vals["supplier_account_no"] or next_supplier_account(c)
                # Re-check account number uniqueness.
                if c.execute("SELECT 1 FROM accounts WHERE supplier_account_no=?", (account,)).fetchone(): account = next_supplier_account(c)
                cur = c.execute("""INSERT INTO accounts(name,type,phone,address,supplier_account_no,email,contact_person,registration_no,vat_no,
                                      payment_terms,credit_limit,currency,active,notes) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                                 (name,"Supplier",vals["phone"],vals["address"],account,vals["email"],vals["contact_person"],vals["registration_no"],vals["vat_no"],vals["payment_terms"],credit,vals["currency"],1 if vals["active"]=="Active" else 0,vals["notes"]))
                sid = cur.lastrowid; self.selected_id = sid; action = "SUPPLIER_CREATED"
            try:
                c.execute("CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,username TEXT,role TEXT,action TEXT,entity_type TEXT,entity_id TEXT,details TEXT,branch_id INTEGER DEFAULT 1)")
                c.execute("INSERT INTO audit_log(event_time,username,role,action,entity_type,entity_id,details,branch_id,event_type) VALUES(datetime('now','localtime'),?,?,?,?,?,?,?,?)",
                          (getattr(self.parent,"cashier_username","Unknown"), getattr(self.parent,"cashier_role",""), action, "supplier", str(sid), f"{name} | Account {vals['supplier_account_no']}", getattr(self.parent,"current_branch_id",1)))
            except Exception as exc:
                _bkpos_logger.warning("Suppressed exception in creditors.py", exc_info=exc)
            c.commit()
            messagebox.showinfo("Supplier Saved", f"{name} has been saved successfully.\n\nSupplier Account: {vals['supplier_account_no']}", parent=self)
            self.refresh()
            self.acc_tree.selection_set(str(sid)); self.acc_tree.focus(str(sid)); self.load_supplier(sid)
        except Exception as e:
            c.rollback(); messagebox.showerror("Save Error", str(e), parent=self)
        finally: c.close()

    def delete_supplier(self):
        if not self.selected_id:
            messagebox.showinfo("Supplier Master", "Select a supplier first.", parent=self); return
        c = conn()
        try:
            r = c.execute("SELECT name,supplier_account_no FROM accounts WHERE id=? AND type='Supplier'", (self.selected_id,)).fetchone()
            if not r: return
            used = c.execute("SELECT COUNT(*) FROM grn_headers WHERE supplier_account=? OR supplier_name=?", (r[1], r[0])).fetchone()[0]
            if used:
                messagebox.showwarning("Cannot Delete Supplier", f"{r[0]} has {used} GRN document(s).\n\nKeep the supplier and set Status to Inactive instead.", parent=self); return
            if not messagebox.askyesno("Delete Supplier", f"Delete {r[0]} ({r[1]})?", parent=self): return
            c.execute("DELETE FROM accounts WHERE id=? AND type='Supplier'", (self.selected_id,)); c.commit()
            self.clear_form(); self.refresh()
        finally: c.close()

    def open_payments(self):
        if not self.selected_id:
            messagebox.showinfo("Supplier Payments","Select a supplier first.",parent=self); return "break"
        SupplierPaymentsWindow(self,self.selected_id); return "break"

    def purchase_history(self):
        if not self.selected_id:
            messagebox.showinfo("Purchase History", "Select a supplier first.", parent=self); return
        self.load_supplier(self.selected_id)
        # The main grid already is the professional purchase history view.
        self.txn_tree.focus_set()
        if self.txn_tree.get_children(): self.txn_tree.selection_set(self.txn_tree.get_children()[0])

    def statement(self):
        if not self.selected_id:
            messagebox.showinfo("Supplier Statement", "Select a supplier first.", parent=self); return
        c = conn()
        try:
            r = c.execute("SELECT supplier_account_no,name,phone,address FROM accounts WHERE id=?", (self.selected_id,)).fetchone()
            if not r: return
            rows = c.execute("SELECT created_at,grn_no,supplier_invoice,reference,total FROM grn_headers WHERE supplier_account=? OR supplier_name=? ORDER BY id DESC", (r[0], r[1])).fetchall()
        finally: c.close()
        w = tk.Toplevel(self); w.title(f"Supplier Statement — {r[1]}"); w.geometry("900x600"); w.configure(bg=BG); w.transient(self)
        tk.Label(w,text="SUPPLIER STATEMENT",font=("Arial",18,"bold"),bg=NAVY,fg=WHITE,pady=12).pack(fill="x")
        tk.Label(w,text=f"Account: {r[0]}    Supplier: {r[1]}\nPhone: {r[2] or 'N/A'}    Address: {r[3] or 'N/A'}",font=("Arial",11,"bold"),bg=WHITE,anchor="w",justify="left",padx=15,pady=10).pack(fill="x",padx=12,pady=12)
        t=ttk.Treeview(w,columns=("date","doc","inv","ref","amt"),show="headings")
        for col,title,width in [("date","Date",130),("doc","GRN No.",130),("inv","Supplier Invoice",180),("ref","Reference",150),("amt","Amount",130)]: t.heading(col,text=title); t.column(col,width=width)
        t.pack(fill="both",expand=True,padx=12,pady=5)
        total=0
        for x in rows:
            total += float(x[4] or 0); t.insert("","end",values=(x[0],x[1],x[2] or "",x[3] or "",f"R {float(x[4] or 0):,.2f}"))
        tk.Label(w,text=f"TOTAL PURCHASES: R {total:,.2f}",font=("Arial",14,"bold"),bg=WHITE,anchor="e",padx=15,pady=10).pack(fill="x",padx=12)
        tk.Button(w,text="CLOSE  ESC",command=w.destroy,bg=NAVY,fg=WHITE,font=("Arial",10,"bold"),width=16).pack(pady=10)
        w.bind("<Escape>",lambda e:w.destroy())

    def close(self):
        try:
            self.unbind_all("<F2>"); self.unbind_all("<F3>"); self.unbind_all("<F4>"); self.unbind_all("<F5>"); self.unbind_all("<F6>"); self.unbind_all("<Escape>")
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in creditors.py", exc_info=exc)
        self.destroy()


# Backward-compatible name used by the existing POS menu.
CreditorsWindow = SupplierMasterWindow

# Professional Accounts Payable extension
def ensure_accounts_payable_schema(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS supplier_payments(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      payment_no TEXT UNIQUE NOT NULL, supplier_id INTEGER NOT NULL,
      payment_date TEXT NOT NULL, amount REAL NOT NULL CHECK(amount>0),
      payment_method TEXT NOT NULL, reference TEXT, notes TEXT,
      created_by TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS supplier_credits(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      credit_no TEXT UNIQUE NOT NULL, supplier_id INTEGER NOT NULL,
      credit_date TEXT NOT NULL, amount REAL NOT NULL CHECK(amount>0),
      reason TEXT, reference TEXT, created_by TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS supplier_payment_allocations(
      id INTEGER PRIMARY KEY AUTOINCREMENT, payment_id INTEGER NOT NULL,
      grn_id INTEGER, amount REAL NOT NULL CHECK(amount>0),
      created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS supplier_payment_reversals(
      id INTEGER PRIMARY KEY AUTOINCREMENT, payment_id INTEGER NOT NULL,
      reversal_no TEXT UNIQUE NOT NULL, reason TEXT NOT NULL,
      created_by TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
    CREATE INDEX IF NOT EXISTS idx_supplier_payments_supplier
      ON supplier_payments(supplier_id,payment_date);
    CREATE INDEX IF NOT EXISTS idx_supplier_credits_supplier
      ON supplier_credits(supplier_id,credit_date);
    """)
    conn.commit()

class SupplierAccountsPayableWindow(tk.Toplevel):
    def __init__(self,parent,db_conn=None):
        super().__init__(parent)
        polish_window(self)
        self.title("Supplier Accounts • Accounts Payable")
        self.geometry("1350x800"); self.minsize(1120,700)
        self.configure(bg="#eef2f7")
        self.conn=db_conn or sqlite3.connect(DB_PATH)
        ensure_accounts_payable_schema(self.conn)
        self.supplier_id=None; self.supplier_name=""
        self._build(); self._load_suppliers()

    def _build(self):
        h=tk.Frame(self,bg="#172033"); h.pack(fill="x")
        tk.Label(h,text="SUPPLIER ACCOUNTS",bg="#172033",fg="white",
                 font=("Arial",23,"bold")).pack(side="left",padx=24,pady=18)
        tk.Label(h,text="Accounts Payable  •  Ledger  •  Payments  •  Credits",
                 bg="#172033",fg="#cbd5e1",font=("Arial",11)).pack(side="left",pady=22)
        top=tk.Frame(self,bg="white",bd=1,relief="solid"); top.pack(fill="x",padx=18,pady=14)
        tk.Label(top,text="SUPPLIER",bg="white",fg="#475569",
                 font=("Arial",10,"bold")).grid(row=0,column=0,sticky="w",padx=12,pady=(10,4))
        self.combo=ttk.Combobox(top,state="readonly",font=("Arial",14))
        self.combo.grid(row=1,column=0,sticky="ew",padx=12,pady=(0,12))
        self.combo.bind("<<ComboboxSelected>>",self._selected)
        top.grid_columnconfigure(0,weight=4)
        for c,t,cmd,bg in [(1,"RECORD PAYMENT",self._payment_dialog,"#16803c"),
                           (2,"SUPPLIER CREDIT",self._credit_dialog,"#b45309"),
                           (3,"REFRESH",self._refresh,"#475569")]:
            tk.Button(top,text=t,command=cmd,bg=bg,fg="white",
                      font=("Arial",12,"bold"),bd=0,padx=20,pady=11).grid(
                      row=1,column=c,padx=6,pady=(0,12),sticky="ew")
        cards=tk.Frame(self,bg="#eef2f7"); cards.pack(fill="x",padx=18)
        self.cards={}
        for i,(k,label) in enumerate([
            ("purchases","TOTAL PURCHASES"),("payments","TOTAL PAYMENTS"),
            ("credits","SUPPLIER CREDITS"),("balance","OUTSTANDING"),
            ("limit","CREDIT LIMIT"),("available","AVAILABLE CREDIT")]):
            cards.grid_columnconfigure(i,weight=1)
            f=tk.Frame(cards,bg="white",bd=1,relief="solid"); f.grid(row=0,column=i,padx=4,sticky="nsew")
            tk.Label(f,text=label,bg="white",fg="#64748b",font=("Arial",9,"bold")).pack(anchor="w",padx=12,pady=(10,3))
            v=tk.StringVar(value="—"); self.cards[k]=v
            tk.Label(f,textvariable=v,bg="white",fg="#172033",font=("Arial",16,"bold")).pack(anchor="w",padx=12,pady=(0,12))
        body=tk.Frame(self,bg="white",bd=1,relief="solid"); body.pack(fill="both",expand=True,padx=18,pady=14)
        tk.Label(body,text="SUPPLIER LEDGER",bg="white",fg="#172033",font=("Arial",14,"bold")).pack(anchor="w",padx=14,pady=(12,6))
        cols=("date","doc","type","desc","debit","credit","balance")
        self.tree=ttk.Treeview(body,columns=cols,show="headings")
        heads={"date":"DATE","doc":"DOCUMENT","type":"TYPE","desc":"DESCRIPTION","debit":"DEBIT","credit":"CREDIT","balance":"BALANCE"}
        widths={"date":105,"doc":145,"type":120,"desc":430,"debit":135,"credit":135,"balance":155}
        for c in cols:
            self.tree.heading(c,text=heads[c]); self.tree.column(c,width=widths[c],anchor="e" if c in ("debit","credit","balance") else "w")
        self.tree.pack(fill="both",expand=True,padx=12,pady=(0,12))
        self.tree.bind("<Double-1>",self._detail)
        f=tk.Frame(self,bg="#172033"); f.pack(fill="x",padx=18,pady=(0,14))
        self.status=tk.StringVar(value="Select a supplier.")
        tk.Label(f,textvariable=self.status,bg="#172033",fg="#cbd5e1",font=("Arial",10,"bold")).pack(side="left",padx=14,pady=10)
        tk.Button(f,text="CLOSE",command=self.destroy,bg="#475569",fg="white",bd=0,font=("Arial",10,"bold"),padx=18,pady=7).pack(side="right",padx=10,pady=7)

    def _load_suppliers(self):
        rows=self.conn.execute("SELECT id,COALESCE(account_no,''),name FROM accounts WHERE type='Supplier' ORDER BY name").fetchall()
        self.rows=rows; self.combo["values"]=[(f"{r[1]}  •  {r[2]}" if r[1] else r[2]) for r in rows]

    def _selected(self,event=None):
        i=self.combo.current()
        if i>=0: self.supplier_id,self.supplier_name=self.rows[i][0],self.rows[i][2]; self._refresh()

    def _sum(self,q,a):
        try:return float(self.conn.execute(q,a).fetchone()[0] or 0)
        except sqlite3.OperationalError:return 0.0

    def _refresh(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        if not self.supplier_id:
            for v in self.cards.values(): v.set("—")
            return
        p=self._sum("SELECT COALESCE(SUM(total_amount),0) FROM grn WHERE supplier_id=?",(self.supplier_id,))
        pay=self._sum("""SELECT COALESCE(SUM(p.amount),0) FROM supplier_payments p
          WHERE p.supplier_id=? AND NOT EXISTS(SELECT 1 FROM supplier_payment_reversals r WHERE r.payment_id=p.id)""",(self.supplier_id,))
        cr=self._sum("SELECT COALESCE(SUM(amount),0) FROM supplier_credits WHERE supplier_id=?",(self.supplier_id,))
        bal=max(0,p-pay-cr); lim=self._sum("SELECT COALESCE(credit_limit,0) FROM accounts WHERE id=?",(self.supplier_id,))
        for k,v in {"purchases":p,"payments":pay,"credits":cr,"balance":bal,"limit":lim,"available":(lim-bal if lim else 0)}.items(): self.cards[k].set(f"R {v:,.2f}")
        entries=[]
        try:
            for rid,no,date,amt in self.conn.execute("SELECT id,COALESCE(grn_no,''),COALESCE(grn_date,created_at,''),COALESCE(total_amount,0) FROM grn WHERE supplier_id=? ORDER BY id",(self.supplier_id,)):
                entries.append((date,no,"PURCHASE","Goods received",float(amt or 0),0))
        except sqlite3.OperationalError:
            _bkpos_logger.warning("Suppressed exception in creditors.py", exc_info=exc)
        for rid,no,date,amt,method,ref in self.conn.execute("SELECT id,payment_no,payment_date,amount,payment_method,reference FROM supplier_payments WHERE supplier_id=? ORDER BY id",(self.supplier_id,)):
            if not self.conn.execute("SELECT 1 FROM supplier_payment_reversals WHERE payment_id=?",(rid,)).fetchone():
                entries.append((date,no,"PAYMENT",f"{method} {ref or ''}".strip(),0,float(amt or 0)))
        for no,date,amt,reason,ref in self.conn.execute("SELECT credit_no,credit_date,amount,reason,reference FROM supplier_credits WHERE supplier_id=? ORDER BY id",(self.supplier_id,)):
            entries.append((date,no,"CREDIT",f"{reason or 'Supplier credit'} {ref or ''}".strip(),0,float(amt or 0)))
        entries.sort(key=lambda x:(x[0] or "",x[1] or ""))
        running=0
        for date,no,typ,desc,debit,credit in entries:
            running+=debit-credit
            self.tree.insert("", "end", values=(date,no,typ,desc,f"R {debit:,.2f}" if debit else "—",f"R {credit:,.2f}" if credit else "—",f"R {running:,.2f}"))
        state="CLEAR" if bal<=.005 else ("OVER LIMIT" if lim and bal>lim else "OWING")
        self.status.set(f"{self.supplier_name}  •  {state}  •  Outstanding R {bal:,.2f}")

    def _payment_dialog(self):
        if not self.supplier_id: messagebox.showwarning("Supplier Required","Select a supplier first.",parent=self); return
        w=tk.Toplevel(self); w.title("Record Supplier Payment"); w.geometry("650x560"); w.transient(self); w.grab_set()
        f=tk.Frame(w,bg="white",bd=1,relief="solid"); f.pack(fill="both",expand=True,padx=20,pady=20)
        tk.Label(f,text="RECORD SUPPLIER PAYMENT",bg="white",fg="#172033",font=("Arial",18,"bold")).pack(anchor="w",padx=24,pady=(20,4))
        tk.Label(f,text=self.supplier_name,bg="white",fg="#64748b",font=("Arial",11)).pack(anchor="w",padx=24,pady=(0,12))
        fields={}
        def add(label,default=""):
            tk.Label(f,text=label,bg="white",fg="#475569",font=("Arial",10,"bold")).pack(anchor="w",padx=24,pady=(6,3))
            e=tk.Entry(f,font=("Arial",14)); e.pack(fill="x",padx=24,ipady=7); e.insert(0,default); fields[label]=e
        add("AMOUNT")
        tk.Label(f,text="PAYMENT METHOD",bg="white",fg="#475569",font=("Arial",10,"bold")).pack(anchor="w",padx=24,pady=(6,3))
        method=ttk.Combobox(f,values=["Cash","Card","Bank Transfer","Other"],state="readonly",font=("Arial",13)); method.set("Bank Transfer"); method.pack(fill="x",padx=24,ipady=6); fields["METHOD"]=method
        add("REFERENCE"); add("DATE",datetime.date.today().isoformat()); add("NOTES")
        def save():
            try:a=float(fields["AMOUNT"].get().replace(",",""))
            except: messagebox.showerror("Invalid Amount","Enter a valid amount.",parent=w); return
            if a<=0:return
            no=f"PAY-{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            self.conn.execute("INSERT INTO supplier_payments(payment_no,supplier_id,payment_date,amount,payment_method,reference,notes,created_by) VALUES(?,?,?,?,?,?,?,?)",
                (no,self.supplier_id,fields["DATE"].get(),a,method.get(),fields["REFERENCE"].get(),fields["NOTES"].get(),os.environ.get("USERNAME","Admin")))
            self.conn.commit(); w.destroy(); self._refresh()
            messagebox.showinfo("Payment Recorded",f"{no}\nR {a:,.2f} recorded.",parent=self)
        tk.Button(f,text="SAVE PAYMENT",command=save,bg="#16803c",fg="white",font=("Arial",14,"bold"),bd=0,pady=12).pack(fill="x",padx=24,pady=18)

    def _credit_dialog(self):
        if not self.supplier_id: messagebox.showwarning("Supplier Required","Select a supplier first.",parent=self); return
        w=tk.Toplevel(self); w.title("Supplier Credit"); w.geometry("620x470"); w.transient(self); w.grab_set()
        f=tk.Frame(w,bg="white",bd=1,relief="solid"); f.pack(fill="both",expand=True,padx=20,pady=20)
        tk.Label(f,text="POST SUPPLIER CREDIT",bg="white",fg="#172033",font=("Arial",18,"bold")).pack(anchor="w",padx=24,pady=(20,15))
        fields={}
        for label,default in [("AMOUNT",""),("DATE",datetime.date.today().isoformat()),("REASON","Damaged / returned goods"),("REFERENCE","")]:
            tk.Label(f,text=label,bg="white",fg="#475569",font=("Arial",10,"bold")).pack(anchor="w",padx=24,pady=(6,3))
            e=tk.Entry(f,font=("Arial",13)); e.pack(fill="x",padx=24,ipady=6); e.insert(0,default); fields[label]=e
        def save():
            try:a=float(fields["AMOUNT"].get().replace(",",""))
            except: messagebox.showerror("Invalid Amount","Enter a valid amount.",parent=w); return
            if a<=0:return
            no=f"SCN-{datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            self.conn.execute("INSERT INTO supplier_credits(credit_no,supplier_id,credit_date,amount,reason,reference,created_by) VALUES(?,?,?,?,?,?,?)",
                (no,self.supplier_id,fields["DATE"].get(),a,fields["REASON"].get(),fields["REFERENCE"].get(),os.environ.get("USERNAME","Admin")))
            self.conn.commit(); w.destroy(); self._refresh()
        tk.Button(f,text="POST SUPPLIER CREDIT",command=save,bg="#b45309",fg="white",font=("Arial",14,"bold"),bd=0,pady=12).pack(fill="x",padx=24,pady=18)

    def _detail(self,event=None):
        s=self.tree.selection()
        if not s:return
        v=self.tree.item(s[0],"values")
        doc=str(v[1]); typ=str(v[2]).upper()
        try:
            if typ == "PURCHASE" and doc.startswith("GRN-"):
                from document_viewer import _open
                row=self.conn.execute("SELECT id FROM grn_headers WHERE grn_no=? LIMIT 1",(doc,)).fetchone()
                if row:
                    _open("GRN",row[0],conn=self.conn,parent=self)
                    return
            messagebox.showinfo("Supplier Ledger Entry",f"Document: {v[1]}\nType: {v[2]}\nDescription: {v[3]}\nDebit: {v[4]}\nCredit: {v[5]}\nBalance: {v[6]}",parent=self)
        except Exception as exc:
            messagebox.showerror("Document Viewer",str(exc),parent=self)

def open_supplier_accounts_payable(parent):
    return SupplierAccountsPayableWindow(parent)
