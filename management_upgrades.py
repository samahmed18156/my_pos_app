from core.logger import logger as _bkpos_logger

import os, sqlite3, shutil, glob
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from datetime import datetime

from core.config import DB_PATH
from services.stock_service import record_stock_movement
from core.document_numbers import next_document_number
from services.cashier_workflow import (ensure_schema as ensure_cashier_workflow_schema, get_open_shift,
    open_shift as workflow_open_shift, record_cash_movement, shift_cash_summary, close_shift as workflow_close_shift)
from ui.window_polish import polish_window
DB_NAME = DB_PATH

def conn():
    return sqlite3.connect(DB_NAME)

def ensure_upgrade_schema():
    c=conn(); cur=c.cursor()
    # Payment detail fields used by shifts, dashboards and audit reports.
    for name, typ in [("amount_tendered","REAL DEFAULT 0"),("change_amount","REAL DEFAULT 0"),
                      ("cash_amount","REAL DEFAULT 0"),("card_amount","REAL DEFAULT 0")]:
        cur.execute("PRAGMA table_info(sales_history)")
        cols=[r[1] for r in cur.fetchall()]
        if name not in cols:
            cur.execute(f"ALTER TABLE sales_history ADD COLUMN {name} {typ}")

    # Product management fields
    fields = [
        ("category","TEXT DEFAULT ''"),
        ("supplier","TEXT DEFAULT ''"),
        ("min_stock","REAL DEFAULT 5"),
        ("active","INTEGER DEFAULT 1"),
    ]
    for name, typ in fields:
        cur.execute("PRAGMA table_info(products)")
        cols=[r[1] for r in cur.fetchall()]
        if name not in cols:
            cur.execute(f"ALTER TABLE products ADD COLUMN {name} {typ}")
    cur.execute("""CREATE TABLE IF NOT EXISTS stock_movements(
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        barcode TEXT, description TEXT, movement_type TEXT, qty REAL,
        qty_before REAL, qty_after REAL, cost_price REAL DEFAULT 0,
        reference TEXT DEFAULT '', reason TEXT DEFAULT '', cashier TEXT DEFAULT 'Unknown')""")
    cur.execute("""CREATE TABLE IF NOT EXISTS cashier_shifts(
        id INTEGER PRIMARY KEY AUTOINCREMENT, cashier TEXT NOT NULL, opened_at DATETIME NOT NULL,
        opening_cash REAL DEFAULT 0, closed_at DATETIME, closing_cash REAL,
        expected_cash REAL, difference REAL, status TEXT DEFAULT 'OPEN')""")
    cur.execute("""CREATE TABLE IF NOT EXISTS grn_headers(
        id INTEGER PRIMARY KEY AUTOINCREMENT, grn_no TEXT UNIQUE, supplier_account TEXT,
        supplier_name TEXT, supplier_invoice TEXT, reference TEXT, vat_mode TEXT,
        subtotal REAL DEFAULT 0, vat REAL DEFAULT 0, total REAL DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP, cashier TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS grn_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT, grn_id INTEGER, barcode TEXT,
        description TEXT, soh_before REAL, order_qty REAL, qty_received REAL,
        cost_price REAL, value REAL)""")
    c.commit(); c.close()

def record_movement(barcode, description, typ, qty, before, after, cost=0, ref="", reason="", cashier="Unknown"):
    """Compatibility wrapper: always use the canonical stock service.

    This is important for older databases where stock_movements still has a
    NOT NULL legacy ``quantity`` column in addition to the newer ``qty``.
    """
    c = conn()
    try:
        record_stock_movement(
            barcode=barcode,
            movement_type=typ,
            quantity=qty,
            reference=ref,
            description=description,
            qty_before=before,
            qty_after=after,
            cost_price=cost,
            reason=reason,
            cashier=cashier,
            conn=c,
        )
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()

class ShiftWindow(tk.Toplevel):
    """Real-shop cashier shift screen backed by the Phase 66 workflow service."""
    def __init__(self,parent):
        super().__init__(parent); polish_window(self); self.parent=parent
        self.title("Cashier Shift / End of Day"); self.geometry("980x720"); self.configure(bg="#eef2f7")
        self.transient(parent); self.grab_set(); ensure_upgrade_schema()
        self.cashier=getattr(parent,"cashier_username","Unknown")
        self.build(); self.refresh()
    def _conn(self):
        c=conn(); ensure_cashier_workflow_schema(c); return c
    def build(self):
        tk.Label(self,text="CASHIER SHIFT / END OF DAY",font=("Arial",18,"bold"),bg="#2c5282",fg="white",pady=12).pack(fill="x")
        self.info=tk.Label(self,text="",font=("Arial",12,"bold"),bg="#eef2f7"); self.info.pack(pady=10)
        f=tk.Frame(self,bg="white",padx=20,pady=12); f.pack(fill="x",padx=20)
        tk.Label(f,text="Opening Cash:",font=("Arial",11,"bold"),bg="white").grid(row=0,column=0,sticky="w")
        self.opening=tk.Entry(f,font=("Arial",12),width=15); self.opening.grid(row=0,column=1,padx=8)
        tk.Button(f,text="OPEN SHIFT",font=("Arial",11,"bold"),bg="#38a169",fg="white",command=self.open_shift).grid(row=0,column=2,padx=8)
        tk.Label(f,text="Cash In/Out:",font=("Arial",10,"bold"),bg="white").grid(row=0,column=3,padx=(18,5))
        self.move_amount=tk.Entry(f,width=10); self.move_amount.grid(row=0,column=4)
        self.move_reason=tk.Entry(f,width=28); self.move_reason.insert(0,"Reason"); self.move_reason.grid(row=0,column=5,padx=5)
        tk.Button(f,text="CASH IN",command=lambda:self.cash_move("PAY_IN")).grid(row=0,column=6,padx=3)
        tk.Button(f,text="CASH OUT",command=lambda:self.cash_move("PAY_OUT")).grid(row=0,column=7,padx=3)
        self.tree=ttk.Treeview(self,columns=("item","amount"),show="headings",height=10)
        for c,h in [("item","Cash Reconciliation"),("amount","Amount")]:
            self.tree.heading(c,text=h); self.tree.column(c,width=500 if c=="item" else 220,anchor="e" if c=="amount" else "w")
        self.tree.pack(fill="x",padx=20,pady=12)
        self.summary=tk.Label(self,text="",justify="left",font=("Arial",12),bg="white",anchor="w",padx=20,pady=12); self.summary.pack(fill="x",padx=20)
        b=tk.Frame(self,bg="#eef2f7"); b.pack(pady=12)
        tk.Button(b,text="REFRESH",font=("Arial",11,"bold"),width=14,command=self.refresh).pack(side="left",padx=6)
        tk.Button(b,text="CLOSE SHIFT",font=("Arial",11,"bold"),bg="#c53030",fg="white",width=14,command=self.close_shift).pack(side="left",padx=6)
    def get_open(self):
        c=self._conn()
        try: return get_open_shift(c,self.cashier)
        finally: c.close()
    def open_shift(self):
        try: amount=float(self.opening.get() or 0)
        except Exception: messagebox.showerror("Invalid","Enter a valid opening cash amount.",parent=self); return
        c=self._conn()
        try: workflow_open_shift(c,cashier=self.cashier,opening_cash=amount); c.commit()
        except Exception as exc: c.rollback(); messagebox.showerror("Cannot Open Shift",str(exc),parent=self); return
        finally: c.close()
        self.refresh()
    def cash_move(self,movement_type):
        r=self.get_open()
        if not r: messagebox.showwarning("Shift","Open a shift first.",parent=self); return
        try: amount=float(self.move_amount.get().strip())
        except Exception: messagebox.showerror("Invalid","Enter a valid cash amount.",parent=self); return
        reason=self.move_reason.get().strip()
        c=self._conn()
        try: record_cash_movement(c,shift_id=r[0],cashier=self.cashier,movement_type=movement_type,amount=amount,reason=reason); c.commit()
        except Exception as exc: c.rollback(); messagebox.showerror("Cash Drawer",str(exc),parent=self); return
        finally: c.close()
        self.move_amount.delete(0,"end"); self.refresh()
    def refresh(self):
        r=self.get_open()
        self.info.config(text=("OPEN SHIFT  •  "+str(r[1])+"  •  Started "+str(r[2]) if r else "NO OPEN SHIFT"))
        for x in self.tree.get_children(): self.tree.delete(x)
        if not r:
            self.summary.config(text="Open a shift to begin tracking cashier cash."); return
        c=self._conn()
        try: s=shift_cash_summary(c,r[0])
        finally: c.close()
        rows=[("Opening float",s["opening_cash"]),("Cash sales",s["cash_sales"]),("Customer account cash",s["customer_cash_payments"]),("Cash in",s["cash_pay_ins"]),("Cash refunds",-s["cash_refunds"]),("Supplier cash payouts",-s["supplier_cash_payouts"]),("Cash expenses",-s["cash_expenses"]),("Cash out",-s["cash_pay_outs"]),("EXPECTED CASH",s["expected_cash"])]
        for label,value in rows: self.tree.insert("","end",values=(label,f"R {value:,.2f}"))
        self.summary.config(text=f"Expected Cash:  R {s['expected_cash']:,.2f}\n\nCount the physical drawer before selecting CLOSE SHIFT.")
    def close_shift(self):
        r=self.get_open()
        if not r: messagebox.showwarning("Shift","No open shift.",parent=self); return
        value=tk.simpledialog.askstring("Close Shift","Enter actual cash counted:",parent=self)
        if value is None: return
        try: actual=float(value)
        except Exception: messagebox.showerror("Invalid","Enter a valid amount.",parent=self); return
        c=self._conn()
        try: result=workflow_close_shift(c,shift_id=r[0],actual_cash=actual); c.commit()
        except Exception as exc: c.rollback(); messagebox.showerror("Cannot Close Shift",str(exc),parent=self); return
        finally: c.close()
        messagebox.showinfo("Shift Closed",f"Expected cash: R {result['expected_cash']:,.2f}\nActual cash: R {result['actual_cash']:,.2f}\nDifference: R {result['difference']:,.2f}",parent=self); self.refresh()

class SalesDashboard(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); polish_window(self); self.parent=parent; self.title("Sales Dashboard"); self.geometry("1100x720"); self.configure(bg="#eef2f7"); self.transient(parent); self.grab_set(); ensure_upgrade_schema(); self.build(); self.refresh()
    def build(self):
        tk.Label(self,text="SALES DASHBOARD — TODAY",font=("Arial",20,"bold"),bg="#2c5282",fg="white",pady=14).pack(fill="x")
        self.cards=tk.Frame(self,bg="#eef2f7"); self.cards.pack(fill="x",padx=15,pady=15)
        self.labels={}
        for i,key in enumerate(["Sales","Transactions","VAT","Profit","Cash","Card"]):
            f=tk.Frame(self.cards,bg="white",bd=1,relief="solid"); f.grid(row=0,column=i,padx=5,sticky="nsew"); self.cards.grid_columnconfigure(i,weight=1)
            tk.Label(f,text=key,font=("Arial",10,"bold"),bg="white").pack(pady=(12,3)); l=tk.Label(f,text="R 0.00",font=("Arial",16,"bold"),bg="white"); l.pack(pady=(0,12)); self.labels[key]=l
        body=tk.Frame(self,bg="white",padx=15,pady=10); body.pack(fill="both",expand=True,padx=20)
        self.tree=ttk.Treeview(body,columns=("product","qty","sales","profit"),show="headings")
        for c,h,w in [("product","Top Product"),("qty","Qty Sold",100),("sales","Sales",130),("profit","Profit",130)]:
            self.tree.heading(c,text=h); self.tree.column(c,width=w)
        self.tree.pack(fill="both",expand=True)
        tk.Button(self,text="REFRESH",font=("Arial",11,"bold"),command=self.refresh).pack(pady=12)
    def refresh(self):
        c=conn(); row=c.execute("""SELECT COALESCE(SUM(total_amount),0),COUNT(*),COALESCE(SUM(total_amount-total_cost),0)
                                  FROM sales_history WHERE date(timestamp)=date('now','localtime')""").fetchone()
        vat=float(row[0] or 0)*15/115; sales=float(row[0] or 0); profit=float(row[2] or 0)
        cash=c.execute("SELECT COALESCE(SUM(total_amount),0) FROM sales_history WHERE date(timestamp)=date('now','localtime') AND lower(payment_type)='cash'").fetchone()[0] or 0
        card=c.execute("SELECT COALESCE(SUM(total_amount),0) FROM sales_history WHERE date(timestamp)=date('now','localtime') AND lower(payment_type)='card'").fetchone()[0] or 0
        vals={"Sales":f"R {sales:,.2f}","Transactions":str(row[1]),"VAT":f"R {vat:,.2f}","Profit":f"R {profit:,.2f}","Cash":f"R {float(cash):,.2f}","Card":f"R {float(card):,.2f}"}
        for k,v in vals.items(): self.labels[k].config(text=v)
        for x in self.tree.get_children(): self.tree.delete(x)
        rows=c.execute("""SELECT si.description,SUM(si.qty),SUM(si.value),SUM(si.value-si.qty*p.cost_price)
                         FROM sale_items si LEFT JOIN products p ON p.barcode=si.barcode
                         JOIN sales_history s ON s.id=si.sale_id
                         WHERE date(s.timestamp)=date('now','localtime') GROUP BY si.barcode ORDER BY SUM(si.value) DESC LIMIT 20""").fetchall()
        for r in rows: self.tree.insert("", "end", values=(r[0],f"{float(r[1]):g}",f"R {float(r[2] or 0):,.2f}",f"R {float(r[3] or 0):,.2f}"))
        c.close()

class ProductManagerWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); polish_window(self); self.parent=parent; self.title("Product Management"); self.geometry("1200x720"); self.configure(bg="#eef2f7"); self.transient(parent); self.grab_set(); ensure_upgrade_schema(); self.build(); self.refresh()
    def build(self):
        tk.Label(self,text="PRODUCT MANAGEMENT",font=("Arial",19,"bold"),bg="#2c5282",fg="white",pady=12).pack(fill="x")
        top=tk.Frame(self,bg="#eef2f7",padx=15,pady=10); top.pack(fill="x")
        tk.Label(top,text="Search:",font=("Arial",11,"bold"),bg="#eef2f7").pack(side="left"); self.search=tk.Entry(top,font=("Arial",12),width=35); self.search.pack(side="left",padx=8); self.search.bind("<KeyRelease>",lambda e:self.refresh())
        tk.Button(top,text="+ ADD PRODUCT",font=("Arial",10,"bold"),bg="#38a169",fg="white",command=self.edit).pack(side="right",padx=5)
        tk.Button(top,text="EDIT SELECTED",font=("Arial",10,"bold"),bg="#2c5282",fg="white",command=self.edit_selected).pack(side="right",padx=5)
        tk.Button(top,text="CATEGORIES",font=("Arial",10,"bold"),command=self.open_categories).pack(side="right",padx=5)
        cols=("barcode","description","category","supplier","cost","sell","stock","margin")
        self.tree=ttk.Treeview(self,columns=cols,show="headings")
        heads={"barcode":"Barcode","description":"Description","category":"Category","supplier":"Supplier","cost":"Cost","sell":"Selling","stock":"SOH","margin":"Margin"}
        widths={"barcode":140,"description":280,"category":140,"supplier":150,"cost":95,"sell":95,"stock":85,"margin":95}
        for c in cols: self.tree.heading(c,text=heads[c]); self.tree.column(c,width=widths[c],anchor="e" if c in ("cost","sell","stock","margin") else "w")
        self.tree.pack(fill="both",expand=True,padx=15,pady=5); self.tree.bind("<Double-1>",lambda e:self.edit_selected())
        self.status=tk.Label(self,text="",bg="#eef2f7",font=("Arial",11,"bold")); self.status.pack(pady=8)
    def refresh(self):
        q=self.search.get().strip() if hasattr(self,"search") else ""
        c=conn(); rows=c.execute("""SELECT barcode,description,COALESCE(category,''),COALESCE(supplier,''),COALESCE(cost_price,0),COALESCE(selling_price,0),COALESCE(soh,0),COALESCE(active,1) FROM products WHERE barcode LIKE ? OR description LIKE ? ORDER BY description""",(f"%{q}%",f"%{q}%")).fetchall(); c.close()
        for x in self.tree.get_children(): self.tree.delete(x)
        out=0
        for r in rows:
            margin=(r[5]-r[4]) if r[5] is not None else 0
            if r[6] <= 0: out += 1
            self.tree.insert("", "end", values=(r[0],r[1],r[2],r[3],f"R {r[4]:.2f}",f"R {r[5]:.2f}",f"{r[6]:g}",f"R {margin:.2f}"))
        self.status.config(text=f"{len(rows)} products   •   {out} out of stock   •   SOH is controlled by GRN, sales and returns")
    def open_categories(self):
        try:
            from product_master_wholesale import CategoryManagerWindow
            CategoryManagerWindow(self)
        except Exception as e:
            messagebox.showerror("Categories", str(e), parent=self)

    def edit_selected(self):
        sel=self.tree.selection()
        if not sel: messagebox.showwarning("Select","Select a product.",parent=self); return
        self.open_pricing(self.tree.item(sel[0],"values")[0])

    def open_pricing_selected(self):
        sel=self.tree.selection()
        if not sel:
            messagebox.showwarning("Select","Select a product first.",parent=self); return
        self.open_pricing(self.tree.item(sel[0],"values")[0])

    def open_pricing(self, barcode):
        try:
            from product_master_wholesale import ProductMasterWindow
            ProductMasterWindow(self, selected_barcode=barcode)
        except TypeError:
            ProductMasterWindow(self)
            try:
                self.winfo_children()[-1].search_var.set(barcode)
            except Exception as exc:
                _bkpos_logger.warning("Suppressed exception in management_upgrades.py", exc_info=exc)
    def edit(self,barcode=None):
        c=conn(); row=None
        if barcode:
            cur=c.execute("SELECT barcode,description,category,supplier,cost_price,selling_price FROM products WHERE barcode=?",(barcode,)); row=cur.fetchone()
        c.close()
        w=tk.Toplevel(self); w.title("Edit Product" if row else "Add Product — Product Management"); w.geometry("520x430"); w.transient(self); w.grab_set()
        labels=["Barcode","Description","Category","Supplier","Cost Price","Selling Price"]
        vars=[tk.StringVar(value=str(v) if v is not None else "") for v in (row or ("","","","","0","0"))]

        tk.Label(w,text="PRODUCT DETAILS",font=("Arial",15,"bold"),bg="#2c5282",fg="white",pady=10).grid(row=0,column=0,columnspan=2,sticky="ew")
        for i,(lab,var) in enumerate(zip(labels,vars), start=1):
            tk.Label(w,text=lab+":",font=("Arial",10,"bold")).grid(row=i,column=0,sticky="w",padx=15,pady=7)
            if lab == "Category":
                combo=ttk.Combobox(w,textvariable=var,state="readonly",font=("Arial",11),width=30)
                combo.grid(row=i,column=1,padx=10,pady=7,sticky="w")
                def load_categories(_e=None, combo=combo):
                    try:
                        c2=conn(); vals2=[r[0] for r in c2.execute("SELECT name FROM product_categories WHERE active=1 ORDER BY name COLLATE NOCASE").fetchall()]; c2.close()
                        combo["values"]=[""]+vals2
                    except Exception: combo["values"]=[""]
                combo.bind("<Button-1>",load_categories); combo.bind("<FocusIn>",load_categories); load_categories()
            elif lab == "Supplier":
                combo=ttk.Combobox(w,textvariable=var,state="readonly",font=("Arial",11),width=30)
                combo.grid(row=i,column=1,padx=10,pady=7,sticky="w")
                def load_suppliers(_e=None, combo=combo):
                    try:
                        c2=conn()
                        a=[r[0] for r in c2.execute("SELECT DISTINCT TRIM(name) FROM accounts WHERE type='Supplier' AND TRIM(COALESCE(name,''))<>'' ORDER BY TRIM(name) COLLATE NOCASE").fetchall()]
                        b=[r[0] for r in c2.execute("SELECT DISTINCT TRIM(supplier) FROM products WHERE TRIM(COALESCE(supplier,''))<>'' ORDER BY TRIM(supplier) COLLATE NOCASE").fetchall()]
                        c2.close(); combo["values"]=[""]+sorted(set(a+b),key=str.casefold)
                    except Exception: combo["values"]=[""]
                combo.bind("<Button-1>",load_suppliers); combo.bind("<FocusIn>",load_suppliers); load_suppliers()
            else:
                tk.Entry(w,textvariable=var,font=("Arial",11),width=32).grid(row=i,column=1,padx=10,pady=7,sticky="w")

        tk.Label(w,text="Stock/SOH is controlled by GRN, sales and returns. New products start at SOH 0.",font=("Arial",9),fg="#555",wraplength=470,justify="left").grid(row=7,column=0,columnspan=2,padx=15,pady=(10,4),sticky="w")
        def save():
            try:
                code,desc,category,supplier=vars[0].get().strip(),vars[1].get().strip(),vars[2].get().strip(),vars[3].get().strip()
                cost=float(vars[4].get() or 0); selling=float(vars[5].get() or 0)
                if not code or not desc: raise ValueError
            except: messagebox.showerror("Invalid","Barcode and description are required, and prices must be numeric.",parent=w); return
            c=conn()
            try:
                exists=c.execute("SELECT barcode FROM products WHERE barcode=?",(code,)).fetchone()
                if exists:
                    c.execute("UPDATE products SET description=?,category=?,supplier=?,cost_price=?,selling_price=? WHERE barcode=?",(desc,category,supplier,cost,selling,code))
                    action="PRODUCT_UPDATED"
                else:
                    c.execute("INSERT INTO products(barcode,description,category,supplier,cost_price,selling_price,soh,active,unit_of_sale,packing) VALUES(?,?,?,?,?,?,?,?,?,?)",(code,desc,category,supplier,cost,selling,0,1,"EA",1))
                    action="PRODUCT_CREATED"
                c.execute("CREATE TABLE IF NOT EXISTS audit_log(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,username TEXT,role TEXT,action TEXT,entity_type TEXT,entity_id TEXT,details TEXT,branch_id INTEGER DEFAULT 1)")
                user=getattr(self.parent,"cashier_username","Unknown"); role=getattr(self.parent,"cashier_role",""); branch=getattr(self.parent,"current_branch_id",1)
                c.execute("INSERT INTO audit_log(event_time,username,role,action,entity_type,entity_id,details,branch_id,event_type) VALUES(datetime('now','localtime'),?,?,?,?,?,?,?,?)",(user,role,action,"product",code,f"{desc} | Retail R {selling:.2f} | Cost R {cost:.2f}",branch,action))
                c.commit(); w.destroy(); self.refresh()
            except Exception as e: c.rollback(); messagebox.showerror("Save Error",str(e),parent=w)
            finally: c.close()
        tk.Button(w,text="SAVE PRODUCT",font=("Arial",11,"bold"),bg="#38a169",fg="white",command=save,width=18).grid(row=8,column=0,columnspan=2,pady=16)
        w.bind("<Escape>",lambda e:w.destroy())

class BackupRestoreWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); polish_window(self); self.parent=parent; self.title("Database Backup & Restore"); self.geometry("650x400"); self.configure(bg="#eef2f7"); self.transient(parent); self.grab_set()
        tk.Label(self,text="DATABASE BACKUP & RESTORE",font=("Arial",17,"bold"),bg="#2c5282",fg="white",pady=14).pack(fill="x")
        tk.Label(self,text="Protect your POS database before major changes.",font=("Arial",11),bg="#eef2f7").pack(pady=18)
        tk.Button(self,text="BACK UP DATABASE",font=("Arial",12,"bold"),bg="#38a169",fg="white",width=28,height=2,command=self.backup).pack(pady=8)
        tk.Button(self,text="RESTORE DATABASE",font=("Arial",12,"bold"),bg="#dd6b20",fg="white",width=28,height=2,command=self.restore).pack(pady=8)
        self.status=tk.Label(self,text="",bg="#eef2f7",wraplength=560); self.status.pack(pady=15)
    def backup(self):
        if not os.path.exists(DB_NAME): messagebox.showerror("Backup","Database not found.",parent=self); return
        default=f"pos_store_backup_{datetime.now():%Y%m%d_%H%M%S}.db"
        target=filedialog.asksaveasfilename(parent=self,initialfile=default,defaultextension=".db",filetypes=[("SQLite database","*.db")])
        if not target:return
        try: shutil.copy2(DB_NAME,target); self.status.config(text=f"Backup created:\n{target}")
        except Exception as e: messagebox.showerror("Backup Error",str(e),parent=self)
    def restore(self):
        source=filedialog.askopenfilename(parent=self,filetypes=[("SQLite database","*.db")])
        if not source:return
        if os.path.abspath(source)==os.path.abspath(DB_NAME): messagebox.showwarning("Restore","Choose a backup file, not the active database.",parent=self); return
        if not messagebox.askyesno("Restore","Restore this database? The current database will be backed up first.",parent=self): return
        try:
            safety=f"pos_store_before_restore_{datetime.now():%Y%m%d_%H%M%S}.db"; shutil.copy2(DB_NAME,safety); shutil.copy2(source,DB_NAME)
            messagebox.showinfo("Restore Complete",f"Restored successfully.\nSafety backup: {safety}\n\nRestart the POS now.",parent=self)
        except Exception as e: messagebox.showerror("Restore Error",str(e),parent=self)

class GRNWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); polish_window(self); self.parent=parent; self.title("Goods Received Note (GRN)"); self.geometry("1250x780"); self.configure(bg="#eef2f7"); self.transient(parent); self.grab_set(); ensure_upgrade_schema(); self.rows=[]; self.build()
    def build(self):
        tk.Label(self,text="GOODS RECEIVED NOTE (GRN)",font=("Arial",18,"bold"),bg="#2c5282",fg="white",pady=12).pack(fill="x")
        h=tk.Frame(self,bg="white",padx=15,pady=12); h.pack(fill="x",padx=15,pady=10)
        self.fields={}
        # Supplier Account and Supplier Name are controlled fields.
        # They can only be populated by the F3 Supplier Lookup; users cannot type arbitrary supplier details.
        for i,(lab,key) in enumerate([("Supplier Account","account"),("Supplier Name","supplier"),("Supplier Invoice","invoice"),("Reference","ref")]):
            tk.Label(h,text=lab+":",font=("Arial",10,"bold"),bg="white").grid(row=i//2,column=(i%2)*2,sticky="w",padx=8,pady=6)
            if key in ("account","supplier"):
                e=tk.Entry(h,font=("Arial",11),width=35,state="readonly",readonlybackground="#f3f4f6")
                e.grid(row=i//2,column=(i%2)*2+1,padx=(8,2),pady=6); self.fields[key]=e
                e.bind("<F3>", self.open_supplier_lookup)
                e.bind("<Return>", self.open_supplier_lookup)
            else:
                e=tk.Entry(h,font=("Arial",11),width=35); e.grid(row=i//2,column=(i%2)*2+1,padx=8,pady=6); self.fields[key]=e
        tk.Button(h,text="F3 LOOKUP",font=("Arial",9,"bold"),bg="#3182ce",fg="white",command=self.open_supplier_lookup,width=12).grid(row=1,column=4,padx=6,pady=6)
        tk.Label(h,text="VAT:",font=("Arial",10,"bold"),bg="white").grid(row=2,column=0,sticky="w",padx=8); self.vatmode=ttk.Combobox(h,values=["Inclusive","Exclusive"],state="readonly",width=32); self.vatmode.set("Inclusive"); self.vatmode.grid(row=2,column=1,padx=8)
        tk.Label(h,text="Date:",font=("Arial",10,"bold"),bg="white").grid(row=2,column=2,sticky="w",padx=8); tk.Label(h,text=datetime.now().strftime("%d %b %Y"),font=("Arial",11,"bold"),bg="white").grid(row=2,column=3,sticky="w",padx=8)
        entry=tk.Frame(self,bg="#eef2f7"); entry.pack(fill="x",padx=15)
        # F3 on the item code opens the existing Product Master catalogue.
        # Barcode/code remains editable for scanner input, but products are never created from GRN.
        self.code=tk.Entry(entry,font=("Arial",12),width=18); self.code.grid(row=0,column=0,padx=4)
        self.qty=tk.Entry(entry,font=("Arial",12),width=10); self.qty.grid(row=0,column=1,padx=4); self.qty.insert(0,"1")
        self.cost=tk.Entry(entry,font=("Arial",12),width=12); self.cost.grid(row=0,column=2,padx=4)
        self.code.bind("<F3>", self.open_product_lookup)
        self.qty.bind("<Return>", lambda e: self.add())
        self.cost.bind("<Return>", lambda e: self.add())
        tk.Label(entry,text="Code / F3 Product Lookup     Qty     Cost",font=("Arial",9,"bold"),bg="#eef2f7").grid(row=1,column=0,columnspan=3)
        tk.Button(entry,text="F3 PRODUCT LOOKUP",font=("Arial",10,"bold"),bg="#3182ce",fg="white",command=self.open_product_lookup).grid(row=0,column=3,padx=6)
        tk.Button(entry,text="ADD ITEM",font=("Arial",10,"bold"),bg="#38a169",fg="white",command=self.add).grid(row=0,column=4,padx=6)
        cols=("code","desc","soh","order","qty","cost","value"); self.tree=ttk.Treeview(self,columns=cols,show="headings",height=18)
        heads=["Code","Description","SOH","Order","Qty Received","Cost","Value"]
        widths=[130,350,90,90,110,110,130]
        for c,h,w in zip(cols,heads,widths): self.tree.heading(c,text=h); self.tree.column(c,width=w,anchor="e" if c in ("soh","order","qty","cost","value") else "w")
        self.tree.pack(fill="both",expand=True,padx=15,pady=8)
        self.total=tk.Label(self,text="Subtotal: R 0.00     VAT: R 0.00     TOTAL: R 0.00",font=("Arial",14,"bold"),bg="white",anchor="e",padx=15,pady=10); self.total.pack(fill="x",padx=15)
        b=tk.Frame(self,bg="#eef2f7"); b.pack(pady=10)
        for text,cmd in [("POST GRN",self.post),("CLEAR",self.clear)]:
            tk.Button(b,text=text,font=("Arial",11,"bold"),width=15,bg="#38a169" if text=="POST GRN" else "#718096",fg="white",command=cmd).pack(side="left",padx=5)
    def _set_readonly_entry(self, entry, value):
        entry.configure(state="normal")
        entry.delete(0, "end")
        entry.insert(0, value or "")
        entry.configure(state="readonly")

    def open_supplier_lookup(self, event=None):
        """F3 lookup of suppliers already created in Creditors/Supplier Master."""
        w=tk.Toplevel(self)
        w.title("Supplier Lookup — F3")
        w.geometry("760x520")
        w.configure(bg="#eef2f7")
        w.transient(self)
        w.grab_set()

        tk.Label(w,text="SUPPLIER LOOKUP",font=("Arial",16,"bold"),bg="#2c5282",fg="white",pady=10).pack(fill="x")
        tk.Label(w,text="Select an existing supplier from Creditors. Supplier Account and Name cannot be typed on the GRN.",font=("Arial",10,"bold"),bg="#eef2f7",fg="#333",pady=8).pack(fill="x")

        top=tk.Frame(w,bg="white",padx=10,pady=10); top.pack(fill="x",padx=12,pady=(0,8))
        tk.Label(top,text="Search:",font=("Arial",10,"bold"),bg="white").pack(side="left")
        search=tk.Entry(top,font=("Arial",12),width=45); search.pack(side="left",padx=8)

        cols=("account","name","phone")
        tree=ttk.Treeview(w,columns=cols,show="headings",height=16)
        for c,h,wd in [("account","Supplier Account",170),("name","Supplier Name",330),("phone","Phone",180)]:
            tree.heading(c,text=h); tree.column(c,width=wd,anchor="w")
        tree.pack(fill="both",expand=True,padx=12,pady=5)

        def load():
            for item in tree.get_children(): tree.delete(item)
            q=search.get().strip()
            c=conn()
            try:
                # Supplier Master creates supplier_account_no. Use name/phone/account as the searchable master fields.
                if q:
                    rows=c.execute("""SELECT supplier_account_no,name,COALESCE(phone,'')
                                     FROM accounts WHERE type='Supplier'
                                     AND (supplier_account_no LIKE ? OR name LIKE ? OR phone LIKE ?)
                                     ORDER BY name COLLATE NOCASE""",(f"%{q}%",f"%{q}%",f"%{q}%")).fetchall()
                else:
                    rows=c.execute("""SELECT supplier_account_no,name,COALESCE(phone,'')
                                     FROM accounts WHERE type='Supplier'
                                     ORDER BY name COLLATE NOCASE""").fetchall()
            except Exception as e:
                messagebox.showerror("Supplier Lookup",f"Unable to load suppliers from Creditors.\n\n{e}",parent=w)
                rows=[]
            finally:
                c.close()
            for row in rows: tree.insert("", "end", values=row)
            if tree.get_children():
                first=tree.get_children()[0]; tree.selection_set(first); tree.focus(first); tree.see(first)

        def choose(event=None):
            sel=tree.selection()
            if not sel:
                return
            vals=tree.item(sel[0],"values")
            self._set_readonly_entry(self.fields["account"], vals[0])
            self._set_readonly_entry(self.fields["supplier"], vals[1])
            w.grab_release(); w.destroy()
            self.fields["invoice"].focus_set()

        search.bind("<KeyRelease>",lambda e: load())
        search.bind("<Down>",lambda e: (tree.focus_set(), tree.selection_set(tree.get_children()[0]) if tree.get_children() else None, "break")[-1] if tree.get_children() else "break")
        tree.bind("<Return>",choose)
        tree.bind("<Double-1>",choose)
        tree.bind("<Escape>",lambda e:(w.grab_release(),w.destroy()))
        search.focus_set()
        load()

        b=tk.Frame(w,bg="#eef2f7",pady=10); b.pack(fill="x")
        tk.Button(b,text="SELECT SUPPLIER",font=("Arial",11,"bold"),bg="#38a169",fg="white",width=18,command=choose).pack(side="left",padx=10)
        tk.Button(b,text="CANCEL  Esc",font=("Arial",11,"bold"),bg="#718096",fg="white",width=18,command=lambda:(w.grab_release(),w.destroy())).pack(side="left")
        tk.Label(b,text="F3 Lookup  •  ↑/↓ Select  •  Enter Choose  •  Esc Close",bg="#eef2f7",fg="#444",font=("Arial",9,"bold")).pack(side="right",padx=10)

    def open_product_lookup(self, event=None):
        """Select an existing product from Product Management for this GRN item.
        GRN never creates products; it only receives stock for products already in the catalogue.
        """
        w=tk.Toplevel(self)
        w.title("Product Lookup — F3")
        w.geometry("900x600")
        w.configure(bg="#eef2f7")
        w.transient(self)
        w.grab_set()

        tk.Label(w,text="PRODUCT LOOKUP",font=("Arial",17,"bold"),bg="#2c5282",fg="white",pady=10).pack(fill="x")
        tk.Label(w,text="Select an existing product from Product Management. GRN is for receiving stock only.",font=("Arial",10,"bold"),bg="#eef2f7",fg="#333",pady=8).pack(fill="x")

        top=tk.Frame(w,bg="white",padx=10,pady=10); top.pack(fill="x",padx=12,pady=(0,8))
        tk.Label(top,text="Search:",font=("Arial",10,"bold"),bg="white").pack(side="left")
        search=tk.Entry(top,font=("Arial",12),width=55); search.pack(side="left",padx=8,fill="x",expand=True)
        tk.Button(top,text="CLEAR",command=lambda:(search.delete(0,"end"),load()),width=9).pack(side="left")

        cols=("barcode","description","category","supplier","soh","cost","retail")
        tree=ttk.Treeview(w,columns=cols,show="headings",height=18)
        for c,h,wd,anchor in [
            ("barcode","Barcode",145,"w"),("description","Description",280,"w"),("category","Category",120,"w"),
            ("supplier","Supplier",150,"w"),("soh","SOH",80,"e"),("cost","Cost",95,"e"),("retail","Retail",95,"e")]:
            tree.heading(c,text=h); tree.column(c,width=wd,anchor=anchor)
        tree.pack(fill="both",expand=True,padx=12,pady=5)

        def load():
            for item in tree.get_children(): tree.delete(item)
            q=search.get().strip()
            c=conn()
            try:
                if q:
                    rows=c.execute("""SELECT barcode,description,COALESCE(category,''),COALESCE(supplier,''),
                                      COALESCE(soh,0),COALESCE(cost_price,0),COALESCE(selling_price,0)
                                      FROM products
                                      WHERE COALESCE(active,1)=1
                                      AND (barcode LIKE ? OR description LIKE ? OR category LIKE ? OR supplier LIKE ?)
                                      ORDER BY description COLLATE NOCASE""",
                                      (f"%{q}%",f"%{q}%",f"%{q}%",f"%{q}%")).fetchall()
                else:
                    rows=c.execute("""SELECT barcode,description,COALESCE(category,''),COALESCE(supplier,''),
                                      COALESCE(soh,0),COALESCE(cost_price,0),COALESCE(selling_price,0)
                                      FROM products WHERE COALESCE(active,1)=1
                                      ORDER BY description COLLATE NOCASE""").fetchall()
            except Exception as e:
                messagebox.showerror("Product Lookup",f"Unable to load products.\n\n{e}",parent=w); rows=[]
            finally: c.close()
            for row in rows:
                tree.insert("", "end", values=(row[0],row[1],row[2],row[3],f"{float(row[4] or 0):g}",f"R {float(row[5] or 0):,.2f}",f"R {float(row[6] or 0):,.2f}"))
            children=tree.get_children()
            if children:
                first=children[0]; tree.selection_set(first); tree.focus(first); tree.see(first)

        def choose(event=None):
            sel=tree.selection()
            if not sel: return "break"
            vals=tree.item(sel[0],"values")
            self.code.delete(0,"end"); self.code.insert(0,vals[0])
            self.cost.delete(0,"end"); self.cost.insert(0,str(vals[5]).replace("R ","").replace(",",""))
            w.grab_release(); w.destroy()
            self.qty.focus_set(); self.qty.selection_range(0,"end")
            return "break"

        def search_down(event=None):
            children=tree.get_children()
            if not children: return "break"
            tree.focus_set()
            cur=tree.focus()
            if cur and cur in children:
                idx=children.index(cur); nxt=children[min(idx+1,len(children)-1)]
            else:
                nxt=children[0]
            tree.selection_set(nxt); tree.focus(nxt); tree.see(nxt)
            return "break"

        def search_up(event=None):
            children=tree.get_children()
            if not children: return "break"
            tree.focus_set()
            cur=tree.focus()
            if cur and cur in children:
                idx=children.index(cur); nxt=children[max(idx-1,0)]
            else:
                nxt=children[0]
            tree.selection_set(nxt); tree.focus(nxt); tree.see(nxt)
            return "break"

        search.bind("<KeyRelease>",lambda e: load())
        search.bind("<Down>",search_down); search.bind("<Up>",search_up); search.bind("<Return>",choose)
        tree.bind("<Return>",choose); tree.bind("<Double-1>",choose)
        tree.bind("<Escape>",lambda e:(w.grab_release(),w.destroy(),self.code.focus_set()))
        w.bind("<Escape>",lambda e:(w.grab_release(),w.destroy(),self.code.focus_set()))
        search.focus_set(); load()

        b=tk.Frame(w,bg="#eef2f7",pady=10); b.pack(fill="x")
        tk.Button(b,text="SELECT PRODUCT",font=("Arial",11,"bold"),bg="#38a169",fg="white",width=18,command=choose).pack(side="left",padx=10)
        tk.Button(b,text="CANCEL  Esc",font=("Arial",11,"bold"),bg="#718096",fg="white",width=18,command=lambda:(w.grab_release(),w.destroy())).pack(side="left")
        tk.Label(b,text="F3 Lookup  •  ↑/↓ Select  •  Enter Choose  •  Esc Close",bg="#eef2f7",fg="#444",font=("Arial",9,"bold")).pack(side="right",padx=10)

    def add(self):
        code=self.code.get().strip(); 
        try:q=float(self.qty.get()); cost=float(self.cost.get())
        except: messagebox.showerror("Invalid","Enter code, quantity and cost price.",parent=self); return
        if not code or q<=0 or cost<0:return
        c=conn(); r=c.execute("SELECT description,soh FROM products WHERE barcode=?",(code,)).fetchone(); c.close()
        if not r: messagebox.showerror("Product","Barcode not found. Add the product first.",parent=self); return
        value=q*cost; self.rows.append((code,r[0],float(r[1] or 0),q,cost,value)); self.tree.insert("", "end",values=(code,r[0],f"{r[1]:g}","",f"{q:g}",f"R {cost:.2f}",f"R {value:.2f}")); self.code.delete(0,"end"); self.qty.delete(0,"end"); self.cost.delete(0,"end"); self.update_total()
    def update_total(self):
        gross=sum(x[5] for x in self.rows); vat=gross*15/115 if self.vatmode.get()=="Inclusive" else gross*15/100; sub=gross-vat if self.vatmode.get()=="Inclusive" else gross; total=gross if self.vatmode.get()=="Inclusive" else gross+vat
        self.total.config(text=f"Subtotal: R {sub:,.2f}     VAT: R {vat:,.2f}     TOTAL: R {total:,.2f}")
    def clear(self):
        self.rows=[]; [self.tree.delete(x) for x in self.tree.get_children()]; self.update_total()
    def post(self):
        if not self.fields["account"].get().strip() or not self.fields["supplier"].get().strip():
            messagebox.showwarning("GRN","Select an existing supplier with F3 before posting the GRN.",parent=self); return
        if not self.rows: messagebox.showwarning("GRN","Add at least one item.",parent=self); return
        if not messagebox.askyesno("Post GRN","Post this GRN and update stock?",parent=self):return
        gross=sum(x[5] for x in self.rows); vat=gross*15/115 if self.vatmode.get()=="Inclusive" else gross*.15; sub=gross-vat if self.vatmode.get()=="Inclusive" else gross; total=gross if self.vatmode.get()=="Inclusive" else gross+vat
        c=conn()
        try:
            cur=c.cursor(); no=next_document_number(c, "grn", "GRN")
            cur.execute("""INSERT INTO grn_headers(grn_no,supplier_account,supplier_name,supplier_invoice,reference,vat_mode,subtotal,vat,total,cashier) VALUES(?,?,?,?,?,?,?,?,?,?)""",(no,self.fields["account"].get(),self.fields["supplier"].get(),self.fields["invoice"].get(),self.fields["ref"].get(),self.vatmode.get(),sub,vat,total,getattr(self.parent,"cashier_username","Unknown"))); gid=cur.lastrowid
            for code,desc,soh,q,cost,value in self.rows:
                cur.execute("UPDATE products SET soh=soh+?,cost_price=? WHERE barcode=?",(q,cost,code))
                cur.execute("""INSERT INTO grn_items(grn_id,barcode,description,soh_before,order_qty,qty_received,cost_price,value) VALUES(?,?,?,?,?,?,?,?)""",(gid,code,desc,soh,0,q,cost,value))
                # Use the shared stock movement service so legacy ledgers that
                # retain a NOT NULL `quantity` column remain compatible.
                record_stock_movement(
                    code, "GRN", q, reference=no, description=desc,
                    qty_before=soh, qty_after=soh + q, cost_price=cost,
                    reason="Goods received",
                    cashier=getattr(self.parent, "cashier_username", "Unknown"),
                    conn=c,
                )
            c.commit(); messagebox.showinfo("GRN Posted",f"{no} posted successfully.\nStock updated for {len(self.rows)} item(s).",parent=self); self.clear()
        except Exception as e:c.rollback(); messagebox.showerror("GRN Error",str(e),parent=self)
        finally:c.close()


def automatic_backup():
    """Create at most one startup backup per day, without interrupting POS startup."""
    try:
        if not os.path.exists(DB_NAME):
            return
        folder = os.path.join(os.path.dirname(os.path.abspath(DB_NAME)), "backups")
        os.makedirs(folder, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d")
        target = os.path.join(folder, f"pos_store_auto_{stamp}.db")
        if not os.path.exists(target):
            shutil.copy2(DB_NAME, target)
        # Keep the 14 newest automatic backups.
        files = sorted(glob.glob(os.path.join(folder, "pos_store_auto_*.db")), key=os.path.getmtime, reverse=True)
        for old in files[14:]:
            try: os.remove(old)
            except OSError:
                _bkpos_logger.warning("Suppressed exception in management_upgrades.py", exc_info=exc)
    except Exception as exc:
        _bkpos_logger.warning("Suppressed exception in management_upgrades.py", exc_info=exc)

def install(app_cls):
    ensure_upgrade_schema()
    automatic_backup()

    # Preserve tendered/change/split details for shift reconciliation.
    try:
        import payment as _payment_module
        _original_get_payment = _payment_module.get_payment
        def _tracked_get_payment(parent, *args, **kwargs):
            result = _original_get_payment(parent, *args, **kwargs)
            if result is not None:
                parent._last_payment_info = dict(result)
            return result
        _payment_module.get_payment = _tracked_get_payment
    except Exception as exc:
        _bkpos_logger.warning("Suppressed exception in management_upgrades.py", exc_info=exc)

    # Record stock movement whenever a completed POS sale changes stock.
    original_checkout = app_cls.checkout
    def checkout_with_movement(self, event=None):
        cart_snapshot = [
            (item.get("code"), item.get("description", ""), float(item.get("qty", 0) or 0),
             float(item.get("cost", 0) or 0))
            for item in self.current_invoice().get("cart", [])
        ]
        before = {}
        if cart_snapshot:
            c = conn()
            for code, _, _, _ in cart_snapshot:
                row = c.execute("SELECT soh FROM products WHERE barcode=?", (code,)).fetchone()
                before[code] = float(row[0]) if row else 0.0
            c.close()
        self._last_payment_info = None
        result = original_checkout(self, event)

        # Attach the payment details to the sale created by checkout.
        try:
            info = getattr(self, "_last_payment_info", None)
            if info:
                c = conn()
                row = c.execute("""SELECT id FROM sales_history
                                  WHERE cashier=? ORDER BY id DESC LIMIT 1""",
                                (getattr(self, "cashier_username", "Unknown"),)).fetchone()
                if row:
                    c.execute("""UPDATE sales_history SET amount_tendered=?, change_amount=?,
                                 cash_amount=?, card_amount=? WHERE id=?""",
                              (float(info.get("amount_tendered", 0) or 0),
                               float(info.get("change", 0) or 0),
                               float(info.get("cash", 0) or 0),
                               float(info.get("card", 0) or 0), row[0]))
                    c.commit()
                c.close()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in management_upgrades.py", exc_info=exc)

        # The core POS checkout already records the signed SALE stock movement
        # in app.py inside the same sale transaction.  Do not insert another
        # movement here; doing so creates duplicate stock-history entries while
        # the actual SOH remains correct.
        return result
    app_cls.checkout = checkout_with_movement

    # Add management tools without changing the existing POS menus/permissions.
    original_create_menu = app_cls.create_menu_bar
    def create_menu_bar(self):
        original_create_menu(self)
        menu = self.nametowidget(self.cget("menu"))
        ops = tk.Menu(menu, tearoff=0)
        ops.add_command(label="💰 Cashier Shift / End of Day",
                        command=lambda: ShiftWindow(self))
        if getattr(self, "is_admin", False) or self.can("can_view_reports"):
            ops.add_command(label="📊 Sales Dashboard",
                            command=lambda: SalesDashboard(self))
        if getattr(self, "is_admin", False):
            ops.add_separator()
            ops.add_command(label="💾 Backup & Restore",
                            command=lambda: BackupRestoreWindow(self))
        menu.add_cascade(label="Management", menu=ops)
    app_cls.create_menu_bar = create_menu_bar

# Professional GRN replaces the legacy GRN window while keeping the existing menu/import workflow.
try:
    from professional_grn import ProfessionalGRNWindow
    GRNWindow = ProfessionalGRNWindow
except Exception as exc:
    _bkpos_logger.warning("Suppressed exception in management_upgrades.py", exc_info=exc)
