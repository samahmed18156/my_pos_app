from core.logger import logger as _bkpos_logger
import os
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

from core.config import DB_PATH
DB_NAME = DB_PATH


def db():
    return sqlite3.connect(DB_NAME)


def ensure_schema():
    c = db()
    cur = c.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS quotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quotation_no TEXT UNIQUE NOT NULL,
            customer_id INTEGER,
            customer_account TEXT,
            customer_name TEXT NOT NULL DEFAULT 'Cash Sale',
            quotation_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            valid_until DATE,
            subtotal REAL NOT NULL DEFAULT 0,
            vat REAL NOT NULL DEFAULT 0,
            total REAL NOT NULL DEFAULT 0,
            discount REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'OPEN',
            notes TEXT DEFAULT '',
            created_by TEXT DEFAULT 'Unknown',
            converted_invoice_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS quotation_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quotation_id INTEGER NOT NULL,
            barcode TEXT,
            description TEXT,
            qty REAL NOT NULL,
            price REAL NOT NULL,
            cost REAL NOT NULL DEFAULT 0,
            value REAL NOT NULL,
            FOREIGN KEY(quotation_id) REFERENCES quotations(id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_quotations_no ON quotations(quotation_no)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_quotations_customer ON quotations(customer_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_quotation_items_q ON quotation_items(quotation_id)")
    c.commit()
    c.close()


def next_quotation_no(cur):
    row = cur.execute("SELECT quotation_no FROM quotations ORDER BY id DESC LIMIT 1").fetchone()
    if not row:
        return "QTN-000001"
    try:
        n = int(str(row[0]).split("-")[-1]) + 1
    except Exception:
        n = 1
    return f"QTN-{n:06d}"


class CustomerLookup(tk.Toplevel):
    def __init__(self, parent, on_select):
        super().__init__(parent)
        self.on_select = on_select
        self.title("Customer Lookup • F3")
        self.geometry("850x560")
        self.minsize(720, 480)
        self.transient(parent)
        self.grab_set()
        self.configure(bg="#eef2f7")

        tk.Label(self, text="CUSTOMER LOOKUP", font=("Arial", 18, "bold"),
                 bg="#243447", fg="white", pady=14).pack(fill="x")
        bar = tk.Frame(self, bg="white", bd=1, relief="solid", padx=12, pady=10)
        bar.pack(fill="x", padx=14, pady=14)
        tk.Label(bar, text="Search", font=("Arial", 10, "bold"), bg="white").pack(side="left")
        self.search = tk.Entry(bar, font=("Arial", 13))
        self.search.pack(side="left", fill="x", expand=True, padx=10, ipady=5)

        wrap = tk.Frame(self, bg="white", bd=1, relief="solid")
        wrap.pack(fill="both", expand=True, padx=14, pady=(0,14))
        self.tree = ttk.Treeview(wrap, columns=("id","account","name","type","phone"), show="headings", selectmode="browse")
        for col, title, width in [("id","ID",70),("account","ACCOUNT",150),("name","CUSTOMER",280),("type","TYPE",110),("phone","PHONE",150)]:
            self.tree.heading(col, text=title)
            self.tree.column(col, width=width, anchor="w")
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)

        foot = tk.Frame(self, bg="white", padx=12, pady=10)
        foot.pack(fill="x", side="bottom")
        tk.Button(foot, text="CANCEL", command=self.destroy, font=("Arial",10,"bold"), padx=18, pady=8).pack(side="right")
        tk.Button(foot, text="SELECT  ENTER", command=self.select, font=("Arial",10,"bold"), bg="#2c5282", fg="white", bd=0, padx=18, pady=8).pack(side="right", padx=8)

        self.search.bind("<KeyRelease>", lambda e: self.refresh())
        self.search.bind("<Down>", lambda e: self.move(1))
        self.search.bind("<Up>", lambda e: self.move(-1))
        self.search.bind("<Return>", lambda e: self.select())
        self.tree.bind("<Return>", lambda e: self.select())
        self.tree.bind("<Double-1>", lambda e: self.select())
        self.bind("<Escape>", lambda e: self.destroy())
        self.rows = []
        self.refresh()
        self.search.focus_force()

    def refresh(self):
        q = self.search.get().strip()
        c = db()
        if q:
            rows = c.execute("SELECT id, COALESCE(phone,''), name, customer_type, phone FROM customers WHERE active=1 AND (name LIKE ? OR phone LIKE ? OR CAST(id AS TEXT) LIKE ?) ORDER BY name", (f"%{q}%",f"%{q}%",f"%{q}%")).fetchall()
        else:
            rows = c.execute("SELECT id, COALESCE(phone,''), name, customer_type, phone FROM customers WHERE active=1 ORDER BY name LIMIT 500").fetchall()
        c.close()
        self.rows = rows
        for i in self.tree.get_children(): self.tree.delete(i)
        for r in rows:
            self.tree.insert("", "end", values=(r[0], r[1] or f"CUST-{r[0]:06d}", r[2], r[3] or "Retail", r[4] or ""))
        if rows:
            first = self.tree.get_children()[0]
            self.tree.selection_set(first)
            self.tree.focus(first)

    def move(self, step):
        ids = self.tree.get_children()
        if not ids: return "break"
        cur = self.tree.focus() or ids[0]
        try: idx = ids.index(cur)
        except ValueError: idx = 0
        idx = max(0, min(len(ids)-1, idx + step))
        self.tree.selection_set(ids[idx]); self.tree.focus(ids[idx]); self.tree.see(ids[idx])
        return "break"

    def select(self):
        ids = self.tree.selection()
        if not ids: return "break"
        idx = self.tree.index(ids[0])
        row = self.rows[idx]
        self.on_select(row[0], row[2], row[3] or "Retail")
        self.destroy()
        return "break"


class QuotationWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        ensure_schema()
        self.parent = parent
        self.title("Quotation • F9")
        self.geometry("1280x820")
        self.minsize(1100, 720)
        self.transient(parent)
        self.grab_set()
        self.configure(bg="#eef2f7")
        self.customer_id = None
        self.customer_type = "Retail"
        self.cart = []
        self.quotation_id = None
        self.build()
        self.new_quotation()

    def build(self):
        head = tk.Frame(self, bg="#2c5282", height=76)
        head.pack(fill="x"); head.pack_propagate(False)
        tk.Label(head, text="QUOTATION", font=("Arial", 20, "bold"), bg="#2c5282", fg="white").pack(side="left", padx=20, pady=12)
        self.lbl_no = tk.Label(head, text="QTN-000001", font=("Arial", 17, "bold"), bg="#2c5282", fg="white")
        self.lbl_no.pack(side="right", padx=20)

        info = tk.Frame(self, bg="white", bd=1, relief="solid", padx=12, pady=10)
        info.pack(fill="x", padx=10, pady=10)
        tk.Label(info, text="CUSTOMER", font=("Arial", 10, "bold"), bg="white", fg="#2c5282").grid(row=0,column=0,columnspan=5,sticky="w",pady=(0,8))
        tk.Label(info,text="Account / No.",font=("Arial",10,"bold"),bg="white").grid(row=1,column=0,sticky="w")
        self.customer_account = tk.Entry(info,font=("Arial",13,"bold"),width=18)
        self.customer_account.grid(row=1,column=1,padx=6,ipady=5)
        tk.Label(info,text="Customer Name",font=("Arial",10,"bold"),bg="white").grid(row=1,column=2,sticky="w",padx=(20,0))
        self.customer_name = tk.Entry(info,font=("Arial",13),width=34)
        self.customer_name.grid(row=1,column=3,padx=6,ipady=5)
        tk.Button(info,text="F3 CUSTOMER LOOKUP",command=self.open_customer_lookup,font=("Arial",10,"bold"),bg="#2563eb",fg="white",bd=0,padx=14,pady=8).grid(row=1,column=4,padx=8)
        tk.Label(info,text="Valid Until",font=("Arial",10,"bold"),bg="white").grid(row=2,column=0,sticky="w",pady=(8,0))
        self.valid_until = tk.Entry(info,font=("Arial",12),width=18)
        self.valid_until.grid(row=2,column=1,padx=6,ipady=4,pady=(8,0))
        tk.Label(info,text="Notes",font=("Arial",10,"bold"),bg="white").grid(row=2,column=2,sticky="w",padx=(20,0),pady=(8,0))
        self.notes = tk.Entry(info,font=("Arial",12),width=52)
        self.notes.grid(row=2,column=3,columnspan=2,sticky="ew",padx=6,ipady=4,pady=(8,0))

        cartbox = tk.Frame(self,bg="white",bd=1,relief="solid")
        cartbox.pack(fill="both",expand=True,padx=10,pady=(0,8))
        tk.Label(cartbox,text="QUOTATION ITEMS",font=("Arial",10,"bold"),bg="white",fg="#2c5282",padx=10,pady=7).pack(anchor="w")
        tw = tk.Frame(cartbox,bg="white"); tw.pack(fill="both",expand=True,padx=8,pady=(0,8))
        self.tree = ttk.Treeview(tw,columns=("code","description","qty","price","value"),show="headings")
        for c,t,w,a in [("code","Barcode / Code",170,"w"),("description","Product Description",500,"w"),("qty","Qty",90,"center"),("price","Price",130,"e"),("value","Value",140,"e")]:
            self.tree.heading(c,text=t); self.tree.column(c,width=w,anchor=a)
        self.tree.pack(side="left",fill="both",expand=True)
        sb=ttk.Scrollbar(tw,orient="vertical",command=self.tree.yview); sb.pack(side="right",fill="y"); self.tree.configure(yscrollcommand=sb.set)

        entry = tk.Frame(self,bg="#e1e8f0",bd=1,relief="solid",padx=10,pady=8)
        entry.pack(fill="x",padx=10,pady=(0,8))
        entry.grid_columnconfigure(1,weight=1)
        tk.Label(entry,text="ADD PRODUCT",font=("Arial",11,"bold"),bg="#e1e8f0",fg="#2c5282").grid(row=0,column=0,columnspan=4,sticky="w",pady=(0,6))
        tk.Label(entry,text="Barcode / Code",font=("Arial",10,"bold"),bg="#e1e8f0").grid(row=1,column=0,sticky="w")
        self.code=tk.Entry(entry,font=("Arial",15,"bold"),width=16); self.code.grid(row=2,column=0,sticky="ew",padx=(0,6),ipady=5)
        tk.Label(entry,text="Description",font=("Arial",10,"bold"),bg="#e1e8f0").grid(row=1,column=1,sticky="w",padx=6)
        self.desc=tk.Entry(entry,font=("Arial",14),width=38,state="readonly"); self.desc.grid(row=2,column=1,sticky="ew",padx=6,ipady=5)
        tk.Label(entry,text="Qty",font=("Arial",10,"bold"),bg="#e1e8f0").grid(row=1,column=2,sticky="w",padx=6)
        self.qty=tk.Entry(entry,font=("Arial",15,"bold"),width=7,justify="center"); self.qty.insert(0,"1"); self.qty.grid(row=2,column=2,sticky="ew",padx=6,ipady=5)
        tk.Label(entry,text="Price",font=("Arial",10,"bold"),bg="#e1e8f0").grid(row=1,column=3,sticky="w",padx=6)
        self.price=tk.Entry(entry,font=("Arial",15,"bold"),width=12,justify="right"); self.price.grid(row=2,column=3,sticky="ew",padx=6,ipady=5)
        btn=tk.Frame(entry,bg="#e1e8f0"); btn.grid(row=3,column=0,columnspan=4,sticky="w",pady=(8,0))
        tk.Button(btn,text="ADD PRODUCT",command=self.add_item,font=("Arial",10,"bold"),bg="#16803c",fg="white",bd=0,padx=18,pady=8).pack(side="left")
        tk.Button(btn,text="CLEAR",command=self.clear_item,font=("Arial",10,"bold"),bg="#64748b",fg="white",bd=0,padx=22,pady=8).pack(side="left",padx=6)
        tk.Button(btn,text="F3 PRODUCT LOOKUP",command=self.product_lookup,font=("Arial",10,"bold"),bg="#2563eb",fg="white",bd=0,padx=16,pady=8).pack(side="left",padx=6)
        tk.Button(btn,text="REMOVE SELECTED",command=self.remove_item,font=("Arial",10,"bold"),bg="#e53e3e",fg="white",bd=0,padx=16,pady=8).pack(side="left",padx=6)

        bottom=tk.Frame(self,bg="white",padx=10,pady=8); bottom.pack(fill="x",padx=10,pady=(0,10))
        self.lbl_sub=tk.Label(bottom,text="Subtotal: R 0.00",font=("Arial",12,"bold"),bg="white"); self.lbl_sub.pack(side="right",padx=14)
        self.lbl_vat=tk.Label(bottom,text="VAT: R 0.00",font=("Arial",12,"bold"),bg="white"); self.lbl_vat.pack(side="right",padx=14)
        self.lbl_total=tk.Label(bottom,text="TOTAL: R 0.00",font=("Arial",15,"bold"),fg="#2c5282",bg="white"); self.lbl_total.pack(side="right",padx=14)

        actions=tk.Frame(self,bg="#eef2f7",pady=6); actions.pack(fill="x",padx=10)
        tk.Button(actions,text="F9 NEW QUOTATION",command=self.new_quotation,font=("Arial",10,"bold"),bg="#38a169",fg="white",bd=0,padx=16,pady=9).pack(side="left")
        tk.Button(actions,text="SAVE QUOTATION",command=self.save,font=("Arial",10,"bold"),bg="#2c5282",fg="white",bd=0,padx=18,pady=9).pack(side="left",padx=6)
        tk.Button(actions,text="OPEN QUOTATIONS",command=self.open_list,font=("Arial",10,"bold"),bg="#2563eb",fg="white",bd=0,padx=16,pady=9).pack(side="left",padx=6)
        tk.Button(actions,text="CONVERT TO INVOICE",command=self.convert_to_invoice,font=("Arial",10,"bold"),bg="#805ad5",fg="white",bd=0,padx=18,pady=9).pack(side="left",padx=6)
        tk.Button(actions,text="PRINT / PDF",command=self.print_pdf,font=("Arial",10,"bold"),bg="#475569",fg="white",bd=0,padx=16,pady=9).pack(side="left",padx=6)
        tk.Button(actions,text="CLOSE",command=self.close,font=("Arial",10,"bold"),padx=18,pady=9).pack(side="right")

        self.customer_account.bind("<F3>", lambda e:self._f3_customer())
        self.customer_name.bind("<F3>", lambda e:self._f3_customer())
        self.code.bind("<Return>", self.exact_product)
        self.qty.bind("<Return>", lambda e:self.add_item())
        self.price.bind("<Return>", lambda e:self.add_item())
        self.code.bind("<F3>", lambda e:self._f3_product())
        self.bind("<F3>", lambda e:self._f3_product())
        self.bind("<Escape>", lambda e:self.close())
        self.tree.bind("<Delete>", lambda e:self.remove_item())
        self.protocol("WM_DELETE_WINDOW", self.close)

    def new_quotation(self):
        c=db(); cur=c.cursor(); no=next_quotation_no(cur); c.close()
        self.quotation_id=None; self.cart=[]; self.customer_id=None; self.customer_type="Retail"
        self.lbl_no.config(text=no)
        self.customer_account.delete(0,tk.END); self.customer_account.insert(0,"CASH")
        self.customer_name.delete(0,tk.END); self.customer_name.insert(0,"Cash Sale")
        self.valid_until.delete(0,tk.END); self.valid_until.insert(0,(datetime.now()+timedelta(days=30)).strftime("%Y-%m-%d"))
        self.notes.delete(0,tk.END); self.clear_item(); self.refresh_cart(); self.code.focus_set()

    def _f3_customer(self):
        """F3 pressed on a customer field: open lookup and stop the key
        event from also bubbling up to the window-level F3 binding
        (which would otherwise also fire the product lookup)."""
        self.open_customer_lookup()
        return "break"

    def open_customer_lookup(self):
        if getattr(self, "_customer_lookup_win", None) is not None:
            try:
                if self._customer_lookup_win.winfo_exists():
                    self._customer_lookup_win.lift()
                    self._customer_lookup_win.focus_force()
                    return
            except Exception as exc:
                _bkpos_logger.warning("Suppressed exception in quotation.py", exc_info=exc)
        try:
            from app import CustomerLookupWindow
            self._customer_lookup_win = CustomerLookupWindow(
                self, initial_query=self.customer_account.get().strip(),
                on_select_callback=self.select_customer)
        except Exception:
            self._customer_lookup_win = CustomerLookup(self, self.select_customer)

    def select_customer(self,cid,name,ctype="Retail",phone=""):
        self.customer_id=cid; self.customer_type=ctype or "Retail"
        self.customer_account.delete(0,tk.END); self.customer_account.insert(0,f"CUST-{int(cid):06d}")
        self.customer_name.delete(0,tk.END); self.customer_name.insert(0,name or "Cash Sale")

    def exact_product(self,event=None):
        code=self.code.get().strip()
        if not code: return "break"
        c=db(); row=c.execute("SELECT barcode,description,selling_price,cost_price FROM products WHERE barcode=?",(code,)).fetchone(); c.close()
        if row: self.select_product(row)
        else: self.product_lookup()
        return "break"

    def _f3_product(self):
        """F3 pressed on the code field or the quotation window itself:
        open the product lookup exactly once and swallow the event so it
        doesn't bubble up and re-trigger a second lookup window."""
        self.product_lookup()
        return "break"

    def product_lookup(self):
        if getattr(self, "_product_lookup_win", None) is not None:
            try:
                if self._product_lookup_win.winfo_exists():
                    self._product_lookup_win.lift()
                    self._product_lookup_win.focus_force()
                    return
            except Exception as exc:
                _bkpos_logger.warning("Suppressed exception in quotation.py", exc_info=exc)
        try:
            from app import F3SearchWindow
            self._product_lookup_win = F3SearchWindow(
                self, initial_query=self.code.get().strip(), on_select_callback=self.select_barcode)
        except Exception as exc:
            messagebox.showerror("Product Lookup",str(exc),parent=self)

    def select_barcode(self,barcode):
        c=db(); row=c.execute("SELECT barcode,description,selling_price,cost_price FROM products WHERE barcode=?",(barcode,)).fetchone(); c.close()
        if row: self.select_product(row)

    def select_product(self,row):
        barcode,desc,retail,cost=row
        price=float(retail or 0)
        if self.customer_id:
            try:
                from customer_pricing import get_customer,get_price_for_sale
                cust=get_customer(self.customer_id)
                price=get_price_for_sale(barcode,float(self.qty.get() or 1),price,cust)
            except Exception as exc:
                _bkpos_logger.warning("Suppressed exception in quotation.py", exc_info=exc)
        self.selected=(barcode,desc,float(price),float(cost or 0))
        self.code.delete(0,tk.END); self.code.insert(0,barcode)
        self.desc.config(state="normal"); self.desc.delete(0,tk.END); self.desc.insert(0,desc); self.desc.config(state="readonly")
        self.price.delete(0,tk.END); self.price.insert(0,f"{price:.2f}"); self.qty.focus_set(); self.qty.select_range(0,tk.END)

    def add_item(self,event=None):
        if not hasattr(self,"selected"): return "break"
        try: qty=float(self.qty.get())
        except Exception: qty=1
        if qty<=0: qty=1
        try: price=float(self.price.get())
        except Exception: price=self.selected[2]
        barcode,desc,_,cost=self.selected
        self.cart.append({"code":barcode,"name":desc,"qty":qty,"price":price,"cost":cost,"value":qty*price})
        self.clear_item(); self.refresh_cart(); self.code.focus_set(); return "break"

    def clear_item(self):
        self.selected=None
        for w in (self.code,self.qty,self.price):
            w.delete(0,tk.END)
        self.qty.insert(0,"1"); self.price.insert(0,"0.00")
        self.desc.config(state="normal"); self.desc.delete(0,tk.END); self.desc.config(state="readonly")

    def remove_item(self):
        sel=self.tree.selection()
        if not sel:return
        idx=self.tree.index(sel[0]); self.cart.pop(idx); self.refresh_cart()

    def refresh_cart(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        total=sum(float(x["value"]) for x in self.cart); vat=total*15/115; sub=total-vat
        for x in self.cart:self.tree.insert("", "end", values=(x["code"],x["name"],f"{x['qty']:g}",f"{x['price']:.2f}",f"{x['value']:.2f}"))
        self.lbl_sub.config(text=f"Subtotal: R {sub:.2f}"); self.lbl_vat.config(text=f"VAT: R {vat:.2f}"); self.lbl_total.config(text=f"TOTAL: R {total:.2f}")

    def save(self):
        if not self.cart: messagebox.showwarning("Empty Quotation","Add at least one product.",parent=self); return
        no=self.lbl_no.cget("text"); total=sum(x["value"] for x in self.cart); vat=total*15/115; sub=total-vat
        c=db(); cur=c.cursor()
        try:
            if self.quotation_id:
                cur.execute("UPDATE quotations SET customer_id=?,customer_account=?,customer_name=?,valid_until=?,subtotal=?,vat=?,total=?,notes=?,updated_at=CURRENT_TIMESTAMP,status=CASE WHEN status='CONVERTED' THEN status ELSE 'OPEN' END WHERE id=?",(self.customer_id,self.customer_account.get().strip(),self.customer_name.get().strip() or "Cash Sale",self.valid_until.get().strip(),sub,vat,total,self.notes.get().strip(),self.quotation_id))
                qid=self.quotation_id; cur.execute("DELETE FROM quotation_items WHERE quotation_id=?",(qid,))
            else:
                cur.execute("INSERT INTO quotations(quotation_no,customer_id,customer_account,customer_name,valid_until,subtotal,vat,total,notes,created_by) VALUES(?,?,?,?,?,?,?,?,?,?)",(no,self.customer_id,self.customer_account.get().strip(),self.customer_name.get().strip() or "Cash Sale",self.valid_until.get().strip(),sub,vat,total,self.notes.get().strip(),getattr(self.parent,"cashier_username","Unknown")))
                qid=cur.lastrowid; self.quotation_id=qid
            for x in self.cart:
                cur.execute("INSERT INTO quotation_items(quotation_id,barcode,description,qty,price,cost,value) VALUES(?,?,?,?,?,?,?)",(qid,x["code"],x["name"],x["qty"],x["price"],x["cost"],x["value"]))
            c.commit(); messagebox.showinfo("Quotation Saved",f"{no} saved successfully.\n\nTotal: R {total:.2f}",parent=self)
        except Exception as exc:
            c.rollback(); messagebox.showerror("Save Quotation",str(exc),parent=self)
        finally:c.close()

    def open_list(self):
        ensure_schema(); QuotationListWindow(self,self.load_quotation)

    def load_quotation(self,qid):
        c=db(); q=c.execute("SELECT * FROM quotations WHERE id=?",(qid,)).fetchone(); items=c.execute("SELECT barcode,description,qty,price,cost,value FROM quotation_items WHERE quotation_id=?",(qid,)).fetchall(); c.close()
        if not q:return
        self.quotation_id=q[0]; self.lbl_no.config(text=q[1]); self.customer_id=q[2]; self.customer_account.delete(0,tk.END); self.customer_account.insert(0,q[3] or "CASH"); self.customer_name.delete(0,tk.END); self.customer_name.insert(0,q[4]); self.valid_until.delete(0,tk.END); self.valid_until.insert(0,q[6] or ""); self.notes.delete(0,tk.END); self.notes.insert(0,q[12] or "")
        self.cart=[{"code":r[0],"name":r[1],"qty":r[2],"price":r[3],"cost":r[4],"value":r[5]} for r in items]; self.refresh_cart()

    def convert_to_invoice(self):
        if not self.cart:
            messagebox.showwarning("Quotation", "Add at least one product before converting.", parent=self)
            return
        if not self.quotation_id:
            self.save()
        if not self.quotation_id or self.parent is None:
            return

        # Never create a second invoice from the same saved quotation.
        c = db()
        row = c.execute("SELECT status, converted_invoice_id, quotation_no FROM quotations WHERE id=?", (self.quotation_id,)).fetchone()
        c.close()
        if not row:
            messagebox.showerror("Convert to Invoice", "The quotation could not be found.", parent=self)
            return
        status, existing_invoice, quotation_no = row
        if str(status).upper() == "CONVERTED" or existing_invoice:
            messagebox.showwarning(
                "Already Converted",
                f"{quotation_no} has already been converted to Invoice {int(existing_invoice):03d}.",
                parent=self
            )
            return

        try:
            iid = self.parent.create_new_invoice(switch_to=True)
            inv = self.parent.current_invoice()
            inv["cart"] = [dict(x) for x in self.cart]
            inv["customer_id"] = self.customer_id
            inv["customer_type"] = self.customer_type or "Retail"
            inv["customer_num"] = self.customer_account.get().strip() or "CASH"
            inv["customer_name"] = self.customer_name.get().strip() or "Cash Sale"
            self.parent.load_current_invoice()

            c = db()
            # Atomic duplicate guard: only OPEN quotations can be converted.
            cur = c.execute(
                "UPDATE quotations SET status='CONVERTED', converted_invoice_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=? AND status<>'CONVERTED' AND converted_invoice_id IS NULL",
                (iid, self.quotation_id)
            )
            if cur.rowcount != 1:
                c.rollback(); c.close()
                # The open invoice was created in memory; remove it so a failed
                # duplicate conversion does not leave an unwanted invoice tab.
                try:
                    self.parent.invoices.pop(iid, None)
                    if self.parent.invoices:
                        self.parent.current_invoice_id = list(self.parent.invoices.keys())[-1]
                        self.parent.load_current_invoice(); self.parent.refresh_invoice_tabs()
                    else:
                        self.parent.create_new_invoice()
                except Exception as exc:
                    _bkpos_logger.warning("Suppressed exception in quotation.py", exc_info=exc)
                messagebox.showwarning("Already Converted", "This quotation was converted by another action and cannot be converted again.", parent=self)
                return
            c.commit(); c.close()
            messagebox.showinfo(
                "Converted to Invoice",
                f"{quotation_no} converted to open Invoice {iid:03d}.\n\n"
                "Customer and pricing were carried across.\n"
                "Stock is NOT affected until the invoice is checked out.",
                parent=self
            )
        except Exception as exc:
            try:
                c.close()
            except Exception as exc:
                _bkpos_logger.warning("Suppressed exception in quotation.py", exc_info=exc)
            messagebox.showerror("Convert to Invoice", str(exc), parent=self)

    def print_pdf(self):
        if not self.cart:
            messagebox.showwarning("Quotation","Add products before printing.",parent=self); return
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            from reportlab.lib.units import mm
            path=os.path.abspath(f"{self.lbl_no.cget('text')}.pdf")
            c=canvas.Canvas(path,pagesize=A4); width,height=A4; y=height-25*mm
            c.setFont("Helvetica-Bold",16); c.drawString(20*mm,y,"QUOTATION"); c.setFont("Helvetica",10); c.drawRightString(width-20*mm,y,self.lbl_no.cget('text')); y-=10*mm
            c.drawString(20*mm,y,f"Customer: {self.customer_name.get()} ({self.customer_account.get()})"); y-=7*mm; c.drawString(20*mm,y,f"Valid Until: {self.valid_until.get()}"); y-=10*mm
            c.setFont("Helvetica-Bold",9); c.drawString(20*mm,y,"Barcode"); c.drawString(55*mm,y,"Description"); c.drawRightString(145*mm,y,"Qty"); c.drawRightString(170*mm,y,"Price"); c.drawRightString(195*mm,y,"Value"); y-=6*mm; c.setFont("Helvetica",9)
            for x in self.cart:
                if y<25*mm:c.showPage(); y=270*mm
                c.drawString(20*mm,y,str(x['code'])[:20]); c.drawString(55*mm,y,str(x['name'])[:48]); c.drawRightString(145*mm,y,f"{x['qty']:g}"); c.drawRightString(170*mm,y,f"{x['price']:.2f}"); c.drawRightString(195*mm,y,f"{x['value']:.2f}"); y-=5*mm
            total=sum(x['value'] for x in self.cart); vat=total*15/115; sub=total-vat; y-=5*mm; c.setFont("Helvetica-Bold",10); c.drawRightString(170*mm,y,f"Subtotal: R {sub:.2f}"); y-=6*mm; c.drawRightString(170*mm,y,f"VAT: R {vat:.2f}"); y-=7*mm; c.drawRightString(170*mm,y,f"TOTAL: R {total:.2f}"); c.save()
            messagebox.showinfo("Quotation PDF",f"PDF created:\n{path}",parent=self)
        except ImportError: messagebox.showwarning("PDF","ReportLab is not installed. The quotation can still be saved.",parent=self)
        except Exception as exc: messagebox.showerror("PDF",str(exc),parent=self)

    def close(self):
        try:self.grab_release()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in quotation.py", exc_info=exc)
        self.destroy()


class QuotationListWindow(tk.Toplevel):
    def __init__(self,parent,on_load):
        super().__init__(parent); self.on_load=on_load; self.title("Open Quotations"); self.geometry("1000x600"); self.transient(parent); self.grab_set(); self.configure(bg="#eef2f7")
        tk.Label(self,text="OPEN QUOTATIONS",font=("Arial",18,"bold"),bg="#243447",fg="white",pady=14).pack(fill="x")
        bar=tk.Frame(self,bg="white",padx=12,pady=10); bar.pack(fill="x",padx=14,pady=14); tk.Label(bar,text="Search",font=("Arial",10,"bold"),bg="white").pack(side="left"); self.search=tk.Entry(bar,font=("Arial",12)); self.search.pack(side="left",fill="x",expand=True,padx=10,ipady=5)
        wrap=tk.Frame(self,bg="white"); wrap.pack(fill="both",expand=True,padx=14,pady=(0,14)); self.tree=ttk.Treeview(wrap,columns=("id","no","date","customer","total","status"),show="headings")
        for c,t,w in [("id","ID",60),("no","QUOTATION",150),("date","DATE",160),("customer","CUSTOMER",300),("total","TOTAL",130),("status","STATUS",110)]:self.tree.heading(c,text=t);self.tree.column(c,width=w,anchor="e" if c=="total" else "w")
        self.tree.pack(side="left",fill="both",expand=True); sb=ttk.Scrollbar(wrap,orient="vertical",command=self.tree.yview);sb.pack(side="right",fill="y");self.tree.configure(yscrollcommand=sb.set)
        foot=tk.Frame(self,bg="white",padx=12,pady=10);foot.pack(fill="x");tk.Button(foot,text="CLOSE",command=self.destroy).pack(side="right");tk.Button(foot,text="OPEN  ENTER",command=self.select,font=("Arial",10,"bold"),bg="#2c5282",fg="white",bd=0,padx=16,pady=8).pack(side="right",padx=8)
        self.search.bind("<KeyRelease>",lambda e:self.refresh());self.search.bind("<Return>",lambda e:self.select());self.tree.bind("<Double-1>",lambda e:self.select());self.bind("<Escape>",lambda e:self.destroy());self.refresh();self.search.focus_force()
    def refresh(self):
        q=self.search.get().strip();c=db();rows=c.execute("SELECT id,quotation_no,quotation_date,customer_name,total,status FROM quotations WHERE quotation_no LIKE ? OR customer_name LIKE ? ORDER BY id DESC",(f"%{q}%",f"%{q}%")).fetchall();c.close();self.rows=rows
        for i in self.tree.get_children():self.tree.delete(i)
        for r in rows:self.tree.insert("", "end", values=(r[0],r[1],r[2],r[3],f"R {r[4]:.2f}",r[5]))
        ids=self.tree.get_children()
        if ids:self.tree.selection_set(ids[0]);self.tree.focus(ids[0])
    def select(self):
        ids=self.tree.selection()
        if not ids:return
        idx=self.tree.index(ids[0]);qid=self.rows[idx][0];self.destroy();self.on_load(qid)


def open_quotation(parent):
    return QuotationWindow(parent)


def install(app_cls):
    original_init = app_cls.__init__
    def init_with_f9(self,*args,**kwargs):
        original_init(self,*args,**kwargs)
        self.bind("<F9>", lambda e: open_quotation(self))
    app_cls.__init__ = init_with_f9
    app_cls.open_quotation = lambda self: open_quotation(self)
    return app_cls
