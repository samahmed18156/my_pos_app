import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from core.config import DB_PATH
from ui.window_polish import polish_window
DB_NAME = DB_PATH


def connect():
    return sqlite3.connect(DB_NAME)


def ensure_schema():
    c = connect(); cur = c.cursor()
    # Customer accounts use the existing customers table as the master.
    cur.execute("""CREATE TABLE IF NOT EXISTS customer_account_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        txn_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        txn_type TEXT NOT NULL,
        reference TEXT,
        description TEXT,
        debit REAL DEFAULT 0,
        credit REAL DEFAULT 0,
        balance_after REAL DEFAULT 0,
        cashier TEXT DEFAULT 'Unknown',
        FOREIGN KEY(customer_id) REFERENCES customers(id)
    )""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cat_customer_date ON customer_account_transactions(customer_id, txn_date, id)")
    # Invoice-level debtor tracking: one credit sale = one debtor invoice.
    cur.execute("""CREATE TABLE IF NOT EXISTS customer_account_invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        sale_id INTEGER NOT NULL UNIQUE,
        invoice_no TEXT NOT NULL,
        invoice_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        total REAL NOT NULL DEFAULT 0,
        paid REAL NOT NULL DEFAULT 0,
        outstanding REAL NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'UNPAID',
        FOREIGN KEY(customer_id) REFERENCES customers(id)
    )""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cai_customer_status ON customer_account_invoices(customer_id,status,invoice_date)")
    cur.execute("""CREATE TABLE IF NOT EXISTS customer_account_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        payment_date DATETIME DEFAULT CURRENT_TIMESTAMP,
        amount REAL NOT NULL,
        payment_method TEXT NOT NULL DEFAULT 'Cash',
        reference TEXT,
        notes TEXT,
        cashier TEXT DEFAULT 'Unknown',
        FOREIGN KEY(customer_id) REFERENCES customers(id)
    )""")
    cur.execute("""CREATE TABLE IF NOT EXISTS customer_account_payment_allocations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        payment_id INTEGER NOT NULL,
        invoice_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        FOREIGN KEY(payment_id) REFERENCES customer_account_payments(id),
        FOREIGN KEY(invoice_id) REFERENCES customer_account_invoices(id)
    )""")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_capa_payment ON customer_account_payment_allocations(payment_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_capa_invoice ON customer_account_payment_allocations(invoice_id)")

    # sales_history/customer master linkage for account reporting.
    cols = {r[1] for r in cur.execute("PRAGMA table_info(sales_history)").fetchall()}
    for name, definition in (
        ("customer_id", "INTEGER"),
        ("customer_account", "TEXT"),
        ("customer_name", "TEXT"),
    ):
        if name not in cols:
            cur.execute(f"ALTER TABLE sales_history ADD COLUMN {name} {definition}")
    c.commit(); c.close()


def customer_info(customer_id):
    ensure_schema(); c = connect()
    row = c.execute("SELECT id,name,phone,credit_limit,active FROM customers WHERE id=?", (customer_id,)).fetchone(); c.close()
    if not row: return None
    return {"id": row[0], "name": row[1], "phone": row[2] or "", "credit_limit": float(row[3] or 0), "active": bool(row[4])}


def balance(customer_id, conn=None):
    own = conn is None
    c = conn or connect()
    row = c.execute("SELECT COALESCE(SUM(debit-credit),0) FROM customer_account_transactions WHERE customer_id=?", (customer_id,)).fetchone()
    if own: c.close()
    return float(row[0] or 0)


def post_transaction(conn, customer_id, txn_type, reference, description, debit=0, credit=0, cashier="Unknown"):
    debit = round(float(debit or 0), 2); credit = round(float(credit or 0), 2)
    if debit < 0 or credit < 0 or (debit and credit):
        raise ValueError("A customer account transaction must have either a positive debit or credit.")
    bal = round(balance(customer_id, conn) + debit - credit, 2)
    cur = conn.execute("""INSERT INTO customer_account_transactions
        (customer_id,txn_type,reference,description,debit,credit,balance_after,cashier)
        VALUES(?,?,?,?,?,?,?,?)""", (customer_id, txn_type, reference, description, debit, credit, bal, cashier))
    return cur.lastrowid, bal


def create_credit_invoice(conn, customer_id, sale_id, invoice_no, total, invoice_date=None):
    """Create the invoice-level debtor balance for a completed POS credit sale."""
    total = round(float(total or 0), 2)
    if total <= 0:
        raise ValueError("Credit invoice total must be greater than zero.")
    invoice_date = invoice_date or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = conn.execute("""INSERT OR IGNORE INTO customer_account_invoices
        (customer_id,sale_id,invoice_no,invoice_date,total,paid,outstanding,status)
        VALUES(?,?,?,?,?,0,?,'UNPAID')""",
        (int(customer_id), int(sale_id), str(invoice_no), invoice_date, total, total))
    return cur.lastrowid


def allocate_customer_payment(conn, customer_id, amount, payment_method="Cash",
                              reference="", notes="", cashier="Unknown"):
    """Post a customer payment and allocate it oldest-invoice-first, allowing partial payments."""
    amount = round(float(amount or 0), 2)
    if amount <= 0:
        raise ValueError("Payment must be greater than zero.")
    customer_id = int(customer_id)
    # Never allow a payment greater than the actual outstanding ledger balance.
    current = balance(customer_id, conn)
    if amount > current + 0.01:
        raise ValueError(f"Payment exceeds the customer's outstanding balance of R {current:,.2f}.")
    cur = conn.execute("""INSERT INTO customer_account_payments
        (customer_id,amount,payment_method,reference,notes,cashier)
        VALUES(?,?,?,?,?,?)""",
        (customer_id, amount, payment_method or "Cash", reference or "", notes or "", cashier or "Unknown"))
    payment_id = cur.lastrowid

    remaining = amount
    invoices = conn.execute("""SELECT id,total,paid,outstanding FROM customer_account_invoices
        WHERE customer_id=? AND outstanding>0.005
        ORDER BY invoice_date ASC, id ASC""", (customer_id,)).fetchall()
    for inv_id,total,paid,outstanding in invoices:
        if remaining <= 0.005:
            break
        apply_amt = min(remaining, float(outstanding))
        new_paid = round(float(paid) + apply_amt, 2)
        new_out = round(float(total) - new_paid, 2)
        status = "PAID" if new_out <= 0.005 else "PART PAID"
        conn.execute("""INSERT INTO customer_account_payment_allocations(payment_id,invoice_id,amount)
                        VALUES(?,?,?)""", (payment_id, inv_id, apply_amt))
        conn.execute("""UPDATE customer_account_invoices SET paid=?,outstanding=?,status=? WHERE id=?""",
                     (new_paid, max(new_out,0), status, inv_id))
        remaining = round(remaining - apply_amt, 2)

    # The ledger remains the authoritative customer balance and is reduced by the full payment.
    _, new_balance = post_transaction(conn, customer_id, "PAYMENT",
        reference or f"PAY-{payment_id:06d}", notes or "Customer payment",
        credit=amount, cashier=cashier)
    return payment_id, new_balance


class CustomerAccountsWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent); polish_window(self); ensure_schema(); self.parent = parent
        self.title("Customer Accounts / Debtors"); self.geometry("1180x720"); self.minsize(1000,620)
        self.transient(parent); self.configure(bg="#eef2f7")
        self.customer_rows=[]; self.customer_id=None
        self._build(); self.refresh_customers()
        self.bind("<Escape>", lambda e:self.destroy()); self.bind("<F2>", lambda e:self.new_customer())
        self.bind("<F5>", lambda e:self.refresh_statement())

    def _build(self):
        tk.Label(self,text="CUSTOMER ACCOUNTS / DEBTORS",font=("Arial",20,"bold"),bg="#243447",fg="white",pady=14).pack(fill="x")
        search=tk.Frame(self,bg="white",padx=12,pady=10); search.pack(fill="x",padx=14,pady=12)
        tk.Label(search,text="Search Customer",font=("Arial",10,"bold"),bg="white").pack(side="left")
        self.search=tk.Entry(search,font=("Arial",13),width=34); self.search.pack(side="left",padx=8,ipady=4)
        self.search.bind("<KeyRelease>",lambda e:self.refresh_customers()); self.search.bind("<Down>",lambda e:self.move(1)); self.search.bind("<Up>",lambda e:self.move(-1)); self.search.bind("<Return>",lambda e:self.select_customer())
        tk.Button(search,text="NEW CUSTOMER",command=self.new_customer,font=("Arial",10,"bold"),bg="#2c5282",fg="white",bd=0,padx=14,pady=7).pack(side="left",padx=5)
        tk.Button(search,text="RECEIVE PAYMENT",command=self.receive_payment,font=("Arial",10,"bold"),bg="#2f855a",fg="white",bd=0,padx=14,pady=7).pack(side="left",padx=5)
        tk.Button(search,text="REFRESH",command=self.refresh_customers,font=("Arial",10,"bold"),padx=12,pady=7).pack(side="left",padx=5)

        body=tk.Frame(self,bg="#eef2f7"); body.pack(fill="both",expand=True,padx=14,pady=(0,14)); body.columnconfigure(0,weight=1); body.columnconfigure(1,weight=2); body.rowconfigure(0,weight=1)
        left=tk.Frame(body,bg="white",bd=1,relief="solid"); left.grid(row=0,column=0,sticky="nsew",padx=(0,7))
        self.tree=ttk.Treeview(left,columns=("account","name","phone","limit","balance"),show="headings",selectmode="browse")
        for c,t,w,a in [("account","ACCOUNT",120,"w"),("name","CUSTOMER",230,"w"),("phone","PHONE",120,"w"),("limit","CREDIT LIMIT",110,"e"),("balance","BALANCE",110,"e")]: self.tree.heading(c,text=t);self.tree.column(c,width=w,anchor=a)
        sb=ttk.Scrollbar(left,orient="vertical",command=self.tree.yview);self.tree.configure(yscrollcommand=sb.set);self.tree.pack(side="left",fill="both",expand=True);sb.pack(side="right",fill="y")
        self.tree.bind("<<TreeviewSelect>>",lambda e:self.select_customer()); self.tree.bind("<Return>",lambda e:self.select_customer())

        right=tk.Frame(body,bg="white",bd=1,relief="solid"); right.grid(row=0,column=1,sticky="nsew",padx=(7,0))
        head=tk.Frame(right,bg="white",padx=16,pady=12);head.pack(fill="x")
        self.lbl_customer=tk.Label(head,text="No customer selected",font=("Arial",15,"bold"),bg="white",fg="#243447");self.lbl_customer.pack(side="left")
        self.lbl_balance=tk.Label(head,text="Balance: R 0.00",font=("Arial",16,"bold"),bg="white",fg="#c53030");self.lbl_balance.pack(side="right")
        self.lbl_limit=tk.Label(right,text="Credit Limit: R 0.00",font=("Arial",10,"bold"),bg="white",fg="#52606d",anchor="w");self.lbl_limit.pack(fill="x",padx=16)

        tk.Label(right,text="UNPAID / PART-PAID INVOICES",font=("Arial",10,"bold"),bg="white",fg="#243447",anchor="w").pack(fill="x",padx=16,pady=(10,3))
        inv_frame=tk.Frame(right,bg="white");inv_frame.pack(fill="x",padx=12)
        self.invoice_tree=ttk.Treeview(inv_frame,columns=("invoice","date","total","paid","outstanding","status"),show="headings",height=6)
        for c,t,w,a in [("invoice","INVOICE",105,"w"),("date","DATE",125,"w"),("total","TOTAL",95,"e"),("paid","PAID",95,"e"),("outstanding","OUTSTANDING",110,"e"),("status","STATUS",95,"w")]:
            self.invoice_tree.heading(c,text=t);self.invoice_tree.column(c,width=w,anchor=a)
        self.invoice_tree.pack(fill="x")
        self.invoice_tree.bind("<Double-1>",lambda e:self.show_invoice_details())

        tk.Label(right,text="ACCOUNT LEDGER",font=("Arial",10,"bold"),bg="white",fg="#243447",anchor="w").pack(fill="x",padx=16,pady=(10,3))
        self.statement=ttk.Treeview(right,columns=("date","type","reference","description","debit","credit","balance"),show="headings",height=9)
        for c,t,w,a in [("date","DATE",135,"w"),("type","TYPE",105,"w"),("reference","REFERENCE",115,"w"),("description","DESCRIPTION",250,"w"),("debit","DEBIT",95,"e"),("credit","CREDIT",95,"e"),("balance","BALANCE",105,"e")]:self.statement.heading(c,text=t);self.statement.column(c,width=w,anchor=a)
        self.statement.pack(fill="both",expand=True,padx=12,pady=6)
        self.statement.bind("<Double-1>", self.show_statement_document)
        tk.Button(right,text="VIEW SELECTED DOCUMENT",command=self.show_statement_document,font=("Arial",10,"bold"),bg="#2b6cb0",fg="white",bd=0,padx=14,pady=7).pack(anchor="e",padx=12,pady=(0,8))
        actions=tk.Frame(right,bg="white",padx=12,pady=10);actions.pack(fill="x")
        tk.Button(actions,text="RECEIVE PAYMENT",command=self.receive_payment,bg="#2f855a",fg="white",font=("Arial",10,"bold"),bd=0,padx=14,pady=8).pack(side="left")
        tk.Button(actions,text="REFRESH STATEMENT  F5",command=self.refresh_statement,font=("Arial",10,"bold"),padx=14,pady=8).pack(side="left",padx=7)
        tk.Button(actions,text="CLOSE",command=self.destroy,padx=16,pady=8).pack(side="right")

    def refresh_customers(self):
        ensure_schema(); q=self.search.get().strip() if hasattr(self,"search") else ""; c=connect()
        rows=c.execute("SELECT id,name,phone,credit_limit FROM customers WHERE active=1 AND (name LIKE ? OR phone LIKE ? OR CAST(id AS TEXT) LIKE ?) ORDER BY name LIMIT 500",(f"%{q}%",f"%{q}%",f"%{q}%")).fetchall(); c.close(); self.customer_rows=rows
        for i in self.tree.get_children():self.tree.delete(i)
        for cid,name,phone,limit in rows:
            bal=balance(cid); self.tree.insert("","end",iid=str(cid),values=(f"CUST-{cid:06d}",name,phone or "",f"R {limit or 0:,.2f}",f"R {bal:,.2f}"))
        ids=self.tree.get_children()
        if ids and not self.customer_id:self.tree.selection_set(ids[0]);self.tree.focus(ids[0]);self.select_customer()
        elif self.customer_id and str(self.customer_id) in ids:self.tree.selection_set(str(self.customer_id));self.tree.focus(str(self.customer_id));self.refresh_statement()

    def move(self,step):
        ids=self.tree.get_children();
        if not ids:return "break"
        cur=self.tree.focus() or ids[0]; idx=ids.index(cur) if cur in ids else 0; idx=max(0,min(len(ids)-1,idx+step));self.tree.selection_set(ids[idx]);self.tree.focus(ids[idx]);self.tree.see(ids[idx]);return "break"

    def select_customer(self):
        sel=self.tree.selection()
        if not sel:return
        self.customer_id=int(sel[0]); self.refresh_statement()

    def refresh_statement(self):
        if not self.customer_id:return
        info=customer_info(self.customer_id); bal=balance(self.customer_id)
        if not info:return
        self.lbl_customer.config(text=f"{info['name']}  •  CUST-{self.customer_id:06d}")
        self.lbl_balance.config(text=f"Balance: R {bal:,.2f}")
        self.lbl_limit.config(text=f"Phone: {info['phone'] or '-'}     Credit Limit: R {info['credit_limit']:,.2f}     Available: R {max(info['credit_limit']-bal,0):,.2f}")
        c=connect()
        inv_rows=c.execute("""SELECT invoice_no,invoice_date,total,paid,outstanding,status
            FROM customer_account_invoices WHERE customer_id=? AND outstanding>0.005
            ORDER BY invoice_date ASC, id ASC""",(self.customer_id,)).fetchall()
        self.invoice_tree.delete(*self.invoice_tree.get_children())
        for inv in inv_rows:
            self.invoice_tree.insert("", "end", values=(inv[0],str(inv[1])[:16],f"R {inv[2]:,.2f}",f"R {inv[3]:,.2f}",f"R {inv[4]:,.2f}",inv[5]))
        rows=c.execute("SELECT id,txn_date,txn_type,COALESCE(reference,''),COALESCE(description,''),debit,credit,balance_after FROM customer_account_transactions WHERE customer_id=? ORDER BY id DESC LIMIT 500",(self.customer_id,)).fetchall();c.close()
        self.statement.delete(*self.statement.get_children())
        for r in rows:
            kind = "SALE" if str(r[2]).upper() in ("INVOICE","SALE") and str(r[3]).startswith("INV-") else ""
            self.statement.insert("","end",iid=f"txn-{r[0]}",values=(str(r[1])[:16],r[2],r[3],r[4],f"R {r[5]:,.2f}",f"R {r[6]:,.2f}",f"R {r[7]:,.2f}"),tags=(kind,))

    def show_statement_document(self,event=None):
        # The button may be used with either the detailed invoice list or the
        # full account statement. Resolve the original sale_id instead of
        # assuming the invoice number is the database primary key.
        try:
            from document_viewer import _open
            # If an invoice row is selected, resolve its stored sale_id.
            inv_sel = self.invoice_tree.selection()
            if inv_sel:
                vals = self.invoice_tree.item(inv_sel[0], "values")
                invoice_no = str(vals[0])
                c = connect()
                row = c.execute(
                    "SELECT sale_id FROM customer_account_invoices WHERE invoice_no=? AND customer_id=? LIMIT 1",
                    (invoice_no, self.customer_id)
                ).fetchone()
                c.close()
                if row and row[0]:
                    _open("SALE", int(row[0]), parent=self)
                    return

            sel=self.statement.selection()
            if not sel:
                messagebox.showinfo("Document Viewer","Select an invoice in the account history first.",parent=self)
                return
            iid=sel[0]
            vals=self.statement.item(iid,"values")
            ref=str(vals[2])
            if ref.startswith("INV-"):
                # Resolve through the debtor invoice table where possible.
                c = connect()
                row = c.execute(
                    "SELECT sale_id FROM customer_account_invoices WHERE invoice_no=? AND customer_id=? LIMIT 1",
                    (ref, self.customer_id)
                ).fetchone()
                c.close()
                sale_id = int(row[0]) if row and row[0] else int(ref.split("-")[-1])
                _open("SALE", sale_id, parent=self)
            elif vals[1] in ("INVOICE","SALE"):
                messagebox.showinfo("Document Viewer","This transaction is not linked to an invoice number yet.",parent=self)
            else:
                messagebox.showinfo("Document Viewer","Select a sale/invoice transaction to view its original document.",parent=self)
        except Exception as exc:
            messagebox.showerror("Document Viewer", str(exc), parent=self)

    def show_invoice_details(self):
        sel=self.invoice_tree.selection()
        if not sel:return
        vals=self.invoice_tree.item(sel[0],"values")
        messagebox.showinfo("Debtor Invoice", f"Invoice: {vals[0]}\nDate: {vals[1]}\nTotal: {vals[2]}\nPaid: {vals[3]}\nOutstanding: {vals[4]}\nStatus: {vals[5]}", parent=self)

    def receive_payment(self):
        if not self.customer_id:
            messagebox.showwarning("Customer Account","Select a customer first.",parent=self);return
        info=customer_info(self.customer_id); bal=balance(self.customer_id)
        if bal <= 0.005:
            messagebox.showinfo("Customer Account","This customer has no outstanding balance.",parent=self);return
        w=tk.Toplevel(self);w.title("Receive Customer Payment");w.geometry("520x440");w.resizable(False,False);w.transient(self);w.grab_set()
        tk.Label(w,text="RECEIVE CUSTOMER PAYMENT",font=("Arial",16,"bold"),fg="#243447").pack(pady=(18,8))
        tk.Label(w,text=f"{info['name']}  •  CUST-{self.customer_id:06d}\nOutstanding Balance: R {bal:,.2f}",font=("Arial",11,"bold")).pack(pady=6)
        frm=tk.Frame(w);frm.pack(fill="x",padx=30,pady=10)
        amount=tk.StringVar(value=f"{bal:.2f}"); method=tk.StringVar(value="Cash"); ref=tk.StringVar(); notes=tk.StringVar()
        fields=[("Amount",amount),("Reference",ref),("Notes",notes)]
        for i,(lab,var) in enumerate(fields):
            tk.Label(frm,text=lab,font=("Arial",10,"bold")).grid(row=i,column=0,sticky="w",pady=7)
            tk.Entry(frm,textvariable=var,font=("Arial",12),width=30).grid(row=i,column=1,pady=7)
        tk.Label(frm,text="Payment Method",font=("Arial",10,"bold")).grid(row=3,column=0,sticky="w",pady=7)
        ttk.Combobox(frm,textvariable=method,values=("Cash","Card","Bank Transfer","Other"),state="readonly",font=("Arial",12),width=28).grid(row=3,column=1,pady=7)
        tk.Label(w,text="Payment is automatically allocated to the oldest unpaid invoices first. Partial payments are supported.",font=("Arial",9),fg="#52606d",wraplength=450).pack(pady=5)
        def save():
            try:amt=float(amount.get().replace(",",""))
            except:messagebox.showerror("Payment","Enter a valid amount.",parent=w);return
            if amt<=0:return
            if amt>bal+0.01:
                messagebox.showwarning("Payment",f"Maximum payment is R {bal:,.2f}.",parent=w);return
            c=connect()
            try:
                pid,new_bal=allocate_customer_payment(c,self.customer_id,amt,method.get(),ref.get().strip(),notes.get().strip(),getattr(self.parent,"cashier_username","Unknown"))
                c.commit()
            except Exception as exc:c.rollback();messagebox.showerror("Payment",str(exc),parent=w);return
            finally:c.close()
            w.destroy();self.refresh_customers();self.refresh_statement()
            messagebox.showinfo("Payment Received",f"Payment PAY-{pid:06d} posted successfully.\n\nAmount received: R {amt:,.2f}\nNew account balance: R {new_bal:,.2f}",parent=self)
        tk.Button(w,text="POST PAYMENT",command=save,bg="#2f855a",fg="white",font=("Arial",11,"bold"),bd=0,padx=22,pady=9).pack(pady=10)
        w.bind("<Return>",lambda e:save());w.bind("<Escape>",lambda e:w.destroy())

    def new_customer(self):
        try:
            from customer_pricing import CustomerPricingWindow
            # Open the existing single customer master rather than creating a second master.
            win=CustomerPricingWindow(self.parent); win.title("Customer & Pricing — Add Customer")
        except Exception as exc:messagebox.showerror("Customer",str(exc),parent=self)


class CustomerAgingWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); polish_window(self);ensure_schema();self.parent=parent;self.title("Customer Aging");self.geometry("900x580");self.transient(parent);self.configure(bg="#eef2f7")
        tk.Label(self,text="CUSTOMER AGING",font=("Arial",18,"bold"),bg="#243447",fg="white",pady=14).pack(fill="x")
        tk.Label(self,text="Outstanding balances are grouped by transaction age. Payments reduce the oldest outstanding exposure first for reporting purposes.",bg="#eef2f7",fg="#52606d",font=("Arial",9),pady=10).pack()
        cols=("account","customer","current","days30","days60","days90","older","total")
        self.tree=ttk.Treeview(self,columns=cols,show="headings")
        for c,t,w in [("account","ACCOUNT",120),("customer","CUSTOMER",210),("current","0–30 DAYS",95),("days30","31–60",95),("days60","61–90",95),("days90","91–120",95),("older","120+",95),("total","TOTAL",110)]:self.tree.heading(c,text=t);self.tree.column(c,width=w,anchor="e" if c not in ("account","customer") else "w")
        self.tree.pack(fill="both",expand=True,padx=14,pady=10)
        tk.Button(self,text="VIEW IN JASPER VIEWER",command=self.view_in_jasperviewer,bg="#2b6cb0",fg="white",padx=18,pady=8).pack(side="left",padx=14,pady=10); tk.Button(self,text="CLOSE",command=self.destroy,padx=18,pady=8).pack(side="right",padx=14,pady=10)
        self.load()
    def view_in_jasperviewer(self):
        try:
            from jasper_reports.report_viewer import open_table_report
            rows=[self.tree.item(i,"values") for i in self.tree.get_children()]
            open_table_report("Customer Aging",["Account","Customer","0-30","31-60","61-90","91-120","120+","Total"],rows,parent=self)
        except Exception as exc: messagebox.showerror("JasperViewer",str(exc),parent=self)

    def load(self):
        c=connect();customers=c.execute("SELECT id,name,credit_limit FROM customers WHERE active=1 ORDER BY name").fetchall();today=datetime.now();self.tree.delete(*self.tree.get_children())
        for cid,name,_limit in customers:
            buckets=[0.0]*5
            rows=c.execute("SELECT txn_date,debit,credit FROM customer_account_transactions WHERE customer_id=?",(cid,)).fetchall()
            # Ledger balance by transaction age; credits are applied against oldest debits first.
            debits=[]; credits=0.0
            for stamp,debit,credit in rows:
                if float(credit or 0)>0:credits+=float(credit or 0)
                if float(debit or 0)>0:
                    try:age=max(0,(today-datetime.fromisoformat(str(stamp).replace(' ','T'))).days)
                    except:age=0
                    debits.append((age,float(debit or 0)))
            remaining_credit=credits
            for age,amt in sorted(debits,key=lambda x:x[0],reverse=True):
                applied=min(amt,remaining_credit);out=amt-applied;remaining_credit-=applied
                if out<=0:continue
                idx=0 if age<=30 else 1 if age<=60 else 2 if age<=90 else 3 if age<=120 else 4;buckets[idx]+=out
            total=sum(buckets)
            if total>0.005:self.tree.insert("","end",values=(f"CUST-{cid:06d}",name,*[f"R {x:,.2f}" for x in buckets],f"R {total:,.2f}"))
        c.close()


def install(app_cls):
    ensure_schema()
    return app_cls
