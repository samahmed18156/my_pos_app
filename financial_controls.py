"""Financial, stock, cash-up and invoice-control tools for Family Supermarket POS."""
from core.logger import logger as _bkpos_logger
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from core.config import DB_PATH
DB_NAME = DB_PATH

def db():
    return sqlite3.connect(DB_NAME)

def ensure_schema():
    c = db();
    try:
        cols={r[1] for r in c.execute("PRAGMA table_info(cashup_records)").fetchall()}
        if cols and "opening_float" not in cols: c.execute("ALTER TABLE cashup_records ADD COLUMN opening_float REAL DEFAULT 0")
        c.commit()
    except Exception: c.rollback()
    finally: c.close()
    c=db(); cur=c.cursor()
    def cols(table):
        cur.execute(f"PRAGMA table_info({table})")
        return {r[1] for r in cur.fetchall()}
    # Payment detail fields used by cash-up/reconciliation.
    for name, typ in [
        ("amount_tendered", "REAL DEFAULT 0"),
        ("change_amount", "REAL DEFAULT 0"),
        ("cash_amount", "REAL DEFAULT 0"),
        ("card_amount", "REAL DEFAULT 0"),
    ]:
        if name not in cols("sales_history"):
            cur.execute(f"ALTER TABLE sales_history ADD COLUMN {name} {typ}")
    # Sales status/control fields
    if "voided" not in cols("sales_history"):
        cur.execute("ALTER TABLE sales_history ADD COLUMN voided INTEGER DEFAULT 0")
    if "voided_at" not in cols("sales_history"):
        cur.execute("ALTER TABLE sales_history ADD COLUMN voided_at DATETIME")
    if "voided_by" not in cols("sales_history"):
        cur.execute("ALTER TABLE sales_history ADD COLUMN voided_by TEXT DEFAULT ''")
    # Stock movement table used by GRN, sales, returns and adjustments.
    cur.execute("""CREATE TABLE IF NOT EXISTS stock_movements(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        barcode TEXT, description TEXT, movement_type TEXT, qty REAL,
        qty_before REAL, qty_after REAL, cost_price REAL DEFAULT 0,
        reference TEXT DEFAULT '', reason TEXT DEFAULT '', cashier TEXT DEFAULT 'Unknown')""")
    cur.execute("""CREATE TABLE IF NOT EXISTS void_history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sale_id INTEGER NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        amount REAL DEFAULT 0,
        cash_amount REAL DEFAULT 0,
        card_amount REAL DEFAULT 0,
        cashier TEXT DEFAULT 'Unknown',
        reason TEXT DEFAULT '')""")
    cur.execute("""CREATE TABLE IF NOT EXISTS cashup_records(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cashup_date TEXT NOT NULL,
        cashier TEXT DEFAULT 'Unknown',
        expected_cash REAL DEFAULT 0,
        actual_cash REAL DEFAULT 0,
        difference REAL DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(cashup_date, cashier))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS transaction_controls(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        control_type TEXT NOT NULL,
        reference TEXT DEFAULT '',
        amount REAL DEFAULT 0,
        status TEXT DEFAULT 'OK',
        notes TEXT DEFAULT '',
        cashier TEXT DEFAULT 'Unknown')""")
    # Backward-compatible migration for existing cash-up records.
    if "opening_float" not in cols("cashup_records"):
        cur.execute("ALTER TABLE cashup_records ADD COLUMN opening_float REAL DEFAULT 0")
    c.commit(); c.close()

def money(v):
    return f"R {float(v or 0):,.2f}"

def _date(v):
    return datetime.strptime(v.strip(), "%Y-%m-%d")

class FinancialControlCenter(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); self.parent=parent
        ensure_schema()
        self.title("POS Financial & Stock Control Center"); self.geometry("1160x720")
        self.minsize(1000,620); self.configure(bg="#eef2f7")
        self.transient(parent); self.grab_set(); self.build(); self.refresh()
    def build(self):
        tk.Label(self,text="POS FINANCIAL & STOCK CONTROL CENTER",
                 font=("Arial",19,"bold"),bg="#2c5282",fg="white",pady=12).pack(fill="x")
        bar=tk.Frame(self,bg="#eef2f7",pady=10); bar.pack(fill="x",padx=15)
        for text,cmd,bg in [
            ("REFRESH",self.refresh,None),
            ("CASH-UP / RECONCILIATION",lambda:CashUpWindow(self.parent),"#38a169"),
            ("STOCK RECONCILIATION",lambda:StockReconciliationWindow(self.parent),"#3182ce"),
            ("INVOICE LIFECYCLE",lambda:InvoiceLifecycleWindow(self.parent),"#805ad5")]:
            tk.Button(bar,text=text,command=cmd,bg=bg if bg else "SystemButtonFace",
                      fg="white" if bg else "black",font=("Arial",10,"bold")).pack(side="left",padx=4)
        if getattr(self.parent,"is_admin",False):
            tk.Button(bar,text="VOID COMPLETED SALE",command=lambda:VoidSaleWindow(self.parent),
                      bg="#c53030",fg="white",font=("Arial",10,"bold")).pack(side="right",padx=4)
        self.cards=tk.Frame(self,bg="#eef2f7"); self.cards.pack(fill="x",padx=15,pady=8)
        self.labels={}
        for i,k in enumerate(["Gross Sales","Credit Notes","Net Sales","VAT","Cost","Profit","Cash","Card"]):
            f=tk.Frame(self.cards,bg="white",bd=1,relief="solid"); f.grid(row=0,column=i,padx=3,sticky="nsew")
            self.cards.grid_columnconfigure(i,weight=1)
            tk.Label(f,text=k,font=("Arial",9,"bold"),bg="white").pack(pady=(8,2))
            l=tk.Label(f,text="R 0.00",font=("Arial",13,"bold"),bg="white"); l.pack(pady=(0,8)); self.labels[k]=l
        body=tk.Frame(self,bg="white",padx=15,pady=10); body.pack(fill="both",expand=True,padx=15,pady=(5,15))
        self.tree=ttk.Treeview(body,columns=("item","value","detail"),show="headings")
        for c,h,w in [("item","Control / Measure",250),("value","Value",160),("detail","Detail",650)]:
            self.tree.heading(c,text=h); self.tree.column(c,width=w)
        self.tree.pack(fill="both",expand=True)
    def refresh(self):
        ensure_schema(); c=db()
        sales=c.execute("""SELECT COALESCE(SUM(total_amount),0),COALESCE(SUM(total_cost),0),COUNT(*)
                          FROM sales_history WHERE COALESCE(voided,0)=0""").fetchone()
        returns=c.execute("""SELECT COALESCE(SUM(total_amount),0),COUNT(*)
                            FROM return_history""").fetchone()
        cash=c.execute("SELECT COALESCE(SUM(cash_amount),0) FROM sales_history WHERE COALESCE(voided,0)=0").fetchone()[0] or 0
        card=c.execute("SELECT COALESCE(SUM(card_amount),0) FROM sales_history WHERE COALESCE(voided,0)=0").fetchone()[0] or 0
        gross,cost,count=map(float,(sales[0] or 0,sales[1] or 0,sales[2] or 0))
        cn=float(returns[0] or 0); net=gross-cn; vat=net*15/115; profit=net-cost
        vals={"Gross Sales":gross,"Credit Notes":cn,"Net Sales":net,"VAT":vat,"Cost":cost,"Profit":profit,"Cash":cash,"Card":card}
        for k,v in vals.items(): self.labels[k].config(text=money(v))
        self.tree.delete(*self.tree.get_children())
        checks=[
            ("Completed sales",int(count), "Voided sales excluded"),
            ("Credit notes",int(returns[1] or 0), f"{money(cn)} deducted from sales"),
            ("Net sales",money(net), f"Gross {money(gross)} − Credit Notes {money(cn)}"),
            ("VAT included",money(vat), "VAT-inclusive formula: net × 15 / 115"),
            ("Gross profit",money(profit), f"Net sales {money(net)} − recorded sale cost {money(cost)}"),
            ("Payment reconciliation",money(float(cash)+float(card)),
             f"Cash {money(cash)} + Card {money(card)}; split allocations retained") ]
        for r in checks: self.tree.insert("","end",values=r)
        c.close()

class CashUpWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); self.parent=parent; ensure_schema()
        self.title("Cash-Up / End of Day Reconciliation"); self.geometry("950x650")
        self.configure(bg="#eef2f7"); self.transient(parent); self.grab_set(); self.build(); self.refresh()
    def build(self):
        tk.Label(self,text="CASH-UP / END-OF-DAY RECONCILIATION",
                 font=("Arial",18,"bold"),bg="#2c5282",fg="white",pady=12).pack(fill="x")
        f=tk.Frame(self,bg="#eef2f7",pady=12); f.pack(fill="x",padx=15)
        tk.Label(f,text="Date (YYYY-MM-DD)",font=("Arial",10,"bold"),bg="#eef2f7").pack(side="left")
        self.date=tk.Entry(f,width=13); self.date.insert(0,datetime.now().strftime("%Y-%m-%d")); self.date.pack(side="left",padx=8)
        tk.Label(f,text="Opening Float",font=("Arial",10,"bold"),bg="#eef2f7").pack(side="left",padx=(18,4))
        self.opening_float=tk.Entry(f,width=12); self.opening_float.insert(0,"0.00"); self.opening_float.pack(side="left",padx=4)
        tk.Label(f,text="Actual Cash Counted",font=("Arial",10,"bold"),bg="#eef2f7").pack(side="left",padx=(18,4))
        self.actual_cash=tk.Entry(f,width=14); self.actual_cash.insert(0,"0.00"); self.actual_cash.pack(side="left",padx=4)
        tk.Button(f,text="CALCULATE",command=self.refresh).pack(side="left",padx=8)
        self.info=tk.Label(self,text="",justify="left",anchor="w",font=("Arial",11,"bold"),bg="white",padx=18,pady=15)
        self.info.pack(fill="x",padx=15,pady=8)
        body=tk.Frame(self,bg="white"); body.pack(fill="both",expand=True,padx=15,pady=8)
        self.tree=ttk.Treeview(body,columns=("method","sales","returns","net"),show="headings")
        for c,h,w in [("method","Payment Method",220),("sales","Sales",180),("returns","Cash Refunds",180),("net","Net Cash/Card",180)]:
            self.tree.heading(c,text=h); self.tree.column(c,width=w,anchor="e" if c!="method" else "w")
        self.tree.pack(fill="both",expand=True,padx=8,pady=8)
        tk.Button(self,text="CLOSE",command=self.destroy,width=12).pack(pady=8)
    def refresh(self):
        try:_date(self.date.get())
        except ValueError:
            messagebox.showerror("Cash-Up","Use YYYY-MM-DD.",parent=self); return
        d=self.date.get().strip(); c=db()
        rows=c.execute("""SELECT COALESCE(payment_type,'Other'),
                                 COALESCE(SUM(total_amount),0),COUNT(*)
                          FROM sales_history
                          WHERE DATE(timestamp)=? AND COALESCE(voided,0)=0
                          GROUP BY payment_type""",(d,)).fetchall()
        cash=c.execute("""SELECT COALESCE(SUM(cash_amount),0) FROM sales_history
                          WHERE DATE(timestamp)=? AND COALESCE(voided,0)=0""",(d,)).fetchone()[0] or 0
        card=c.execute("""SELECT COALESCE(SUM(card_amount),0) FROM sales_history
                          WHERE DATE(timestamp)=? AND COALESCE(voided,0)=0""",(d,)).fetchone()[0] or 0
        cash_refund=c.execute("""SELECT COALESCE(SUM(total_amount),0) FROM return_history
                                WHERE DATE(timestamp)=? AND lower(refund_type)='cash refund'""",(d,)).fetchone()[0] or 0
        credit=c.execute("""SELECT COALESCE(SUM(total_amount),0) FROM return_history
                           WHERE DATE(timestamp)=? AND lower(refund_type) LIKE 'credit note%'""",(d,)).fetchone()[0] or 0
        gross=sum(float(r[1] or 0) for r in rows)
        try:
            actual_cash=float(self.actual_cash.get().replace("R","").replace(",","").strip() or 0)
        except ValueError:
            messagebox.showerror("Cash-Up","Enter a valid actual cash amount.",parent=self); return
        try:
            opening=float(self.opening_float.get().replace("R","").replace(",","").strip() or 0)
        except ValueError:
            messagebox.showerror("Cash-Up","Enter a valid opening float.",parent=self); return
        expected_cash=opening+float(cash or 0)-float(cash_refund or 0)
        difference=actual_cash-expected_cash
        self.tree.delete(*self.tree.get_children())
        for method,total,count in rows:
            self.tree.insert("","end",values=(f"{method} ({count})",money(total),"R 0.00",money(total)))
        self.info.config(text=f"Date: {d}\n"
            f"Gross sales: {money(gross)}    Credit Notes: -{money(credit)}    "
            f"Net sales: {money(gross-credit)}\n"
            f"Cash received: {money(cash)}    Card received: {money(card)}    "
            f"Cash refunds: -{money(cash_refund)}\n"
            f"Opening float: {money(opening)}    Expected cash: {money(expected_cash)}    Actual counted: {money(actual_cash)}    "
            f"Difference: {money(difference)}")
        cashier=getattr(self.parent,"cashier_username","Unknown")
        c.execute("""INSERT INTO cashup_records(cashup_date,cashier,opening_float,expected_cash,actual_cash,difference)
                     VALUES(?,?,?,?,?)
                     ON CONFLICT(cashup_date,cashier) DO UPDATE SET
                     expected_cash=excluded.expected_cash,actual_cash=excluded.actual_cash,
                     difference=excluded.difference,created_at=CURRENT_TIMESTAMP""",
                  (d,cashier,opening,expected_cash,actual_cash,difference))
        c.commit()
        c.close()

class StockReconciliationWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); self.parent=parent; ensure_schema()
        self.title("Stock Reconciliation"); self.geometry("1150x700"); self.configure(bg="#eef2f7")
        self.transient(parent); self.grab_set(); self.build(); self.refresh()
    def build(self):
        tk.Label(self,text="STOCK RECONCILIATION",
                 font=("Arial",18,"bold"),bg="#2c5282",fg="white",pady=12).pack(fill="x")
        f=tk.Frame(self,bg="#eef2f7",pady=10); f.pack(fill="x",padx=15)
        tk.Label(f,text="From").pack(side="left"); self.a=tk.Entry(f,width=12); self.a.insert(0,datetime.now().strftime("%Y-%m-%d")); self.a.pack(side="left",padx=5)
        tk.Label(f,text="To").pack(side="left"); self.b=tk.Entry(f,width=12); self.b.insert(0,datetime.now().strftime("%Y-%m-%d")); self.b.pack(side="left",padx=5)
        tk.Button(f,text="RUN",command=self.refresh).pack(side="left",padx=6)
        tk.Button(f,text="VIEW IN JASPER VIEWER",command=self.view_in_jasperviewer).pack(side="left",padx=6)
        self.summary=tk.Label(self,text="",font=("Arial",11,"bold"),bg="#eef2f7",anchor="w",justify="left"); self.summary.pack(fill="x",padx=15,pady=5)
        body=tk.Frame(self,bg="white"); body.pack(fill="both",expand=True,padx=15,pady=8)
        cols=("code","desc","sale","grn","return","adjust","void","net","soh")
        self.tree=ttk.Treeview(body,columns=cols,show="headings")
        heads={"code":"Code","desc":"Description","sale":"Sales","grn":"GRN","return":"Credit Notes/Returns","adjust":"Adjustments","void":"Voids","net":"Net Movement","soh":"Current SOH"}
        widths={"code":125,"desc":250,"sale":80,"grn":80,"return":120,"adjust":100,"void":80,"net":110,"soh":100}
        for c in cols:self.tree.heading(c,text=heads[c]);self.tree.column(c,width=widths[c],anchor="e" if c not in ("code","desc") else "w")
        self.tree.pack(fill="both",expand=True,padx=5,pady=5)
    def view_in_jasperviewer(self):
        try:
            from jasper_reports.report_viewer import open_table_report
            rows=[self.tree.item(i,"values") for i in self.tree.get_children()]
            open_table_report("Stock Reconciliation",["Code","Description","Sales","GRN","Credit Notes/Returns","Adjustments","Voids","Net Movement","Current SOH"],rows,period=f"{self.a.get()} to {self.b.get()}",parent=self)
        except Exception as exc: messagebox.showerror("JasperViewer",str(exc),parent=self)
    def refresh(self):
        try:_date(self.a.get()); _date(self.b.get())
        except ValueError:
            messagebox.showerror("Stock Reconciliation","Use YYYY-MM-DD.",parent=self); return
        a,b=self.a.get().strip(),self.b.get().strip(); c=db()
        products=c.execute("SELECT barcode,description,COALESCE(soh,0) FROM products ORDER BY description").fetchall()
        self.tree.delete(*self.tree.get_children()); moved=0
        for code,desc,soh in products:
            rows=c.execute("""SELECT UPPER(COALESCE(movement_type,'')),COALESCE(SUM(qty),0)
                              FROM stock_movements WHERE barcode=? AND DATE(timestamp) BETWEEN ? AND ?
                              GROUP BY UPPER(COALESCE(movement_type,''))""",(code,a,b)).fetchall()
            d={str(t):float(q or 0) for t,q in rows}
            sale=d.get("SALE",0); grn=d.get("GRN",0); ret=d.get("RETURN",0)
            adj=sum(q for t,q in d.items() if t not in ("SALE","GRN","RETURN","VOID"))
            void=d.get("VOID",0); net=sale+grn+ret+adj+void
            if any(abs(x)>1e-9 for x in (sale,grn,ret,adj,void)):
                self.tree.insert("","end",values=(code,desc,f"{sale:g}",f"{grn:g}",f"{ret:g}",f"{adj:g}",f"{void:g}",f"{net:g}",f"{float(soh):g}")); moved+=1
        self.summary.config(text=f"Products with movements: {moved}  |  SALE quantities are negative; GRN/RETURN/VOID are positive.\n"
                                  "Net Movement is the signed movement recorded during the selected period.")
        c.close()

class InvoiceLifecycleWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); self.parent=parent; ensure_schema()
        self.title("Invoice Lifecycle"); self.geometry("1020x640"); self.configure(bg="#eef2f7")
        self.transient(parent); self.grab_set(); self.build(); self.refresh()
    def build(self):
        tk.Label(self,text="INVOICE LIFECYCLE",
                 font=("Arial",18,"bold"),bg="#2c5282",fg="white",pady=12).pack(fill="x")
        self.info=tk.Label(self,text="",bg="#eef2f7",font=("Arial",11,"bold"),anchor="w",justify="left")
        self.info.pack(fill="x",padx=15,pady=10)
        body=tk.Frame(self,bg="white"); body.pack(fill="both",expand=True,padx=15,pady=5)
        self.tree=ttk.Treeview(body,columns=("id","state","total","payment","cashier","date"),show="headings")
        for c,h,w in [("id","Invoice #",90),("state","State",180),("total","Total",120),("payment","Payment",130),("cashier","Cashier",130),("date","Date",230)]:
            self.tree.heading(c,text=h); self.tree.column(c,width=w,anchor="center")
        self.tree.pack(fill="both",expand=True,padx=5,pady=5)
        tk.Button(self,text="REFRESH",command=self.refresh).pack(side="left",padx=20,pady=10)
        tk.Button(self,text="CLOSE",command=self.destroy).pack(side="right",padx=20,pady=10)
    def refresh(self):
        self.tree.delete(*self.tree.get_children()); open_count=0
        for iid,inv in getattr(self.parent,"invoices",{}).items():
            total=sum(float(x.get("value",0) or 0) for x in inv.get("cart",[]))
            self.tree.insert("","end",values=(f"{iid:03d}","OPEN / UNPOSTED",money(total),"Not posted",
                                               getattr(self.parent,"cashier_username","Unknown"),"Current POS")); open_count+=1
        c=db()
        rows=c.execute("""SELECT id,total_amount,payment_type,cashier,timestamp,COALESCE(voided,0)
                          FROM sales_history ORDER BY id DESC LIMIT 100""").fetchall(); c.close()
        for sid,total,pay,cashier,stamp,voided in rows:
            self.tree.insert("","end",values=(f"{sid:03d}","VOIDED" if voided else "CONFIRMED / POSTED",
                                               money(total),pay or "",cashier or "",stamp or ""))
        self.info.config(text=f"Open invoices: {open_count}  |  Recent posted invoices: {len(rows)}\n"
                              "Lifecycle: OPEN → CONFIRMED/POSTED → optional CREDIT NOTE/RETURN or VOID.")

class VoidSaleWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); self.parent=parent; ensure_schema()
        self.title("Void Completed Sale"); self.geometry("700x470"); self.configure(bg="#eef2f7")
        self.transient(parent); self.grab_set(); self.build()
    def build(self):
        tk.Label(self,text="VOID COMPLETED SALE",
                 font=("Arial",18,"bold"),bg="#c53030",fg="white",pady=12).pack(fill="x")
        f=tk.Frame(self,bg="white",padx=20,pady=18); f.pack(fill="x",padx=20,pady=20)
        tk.Label(f,text="Invoice / Sale #",font=("Arial",11,"bold"),bg="white").grid(row=0,column=0,sticky="w",pady=7)
        self.sid=tk.Entry(f,font=("Arial",12),width=20); self.sid.grid(row=0,column=1,pady=7)
        tk.Label(f,text="Reason",font=("Arial",11,"bold"),bg="white").grid(row=1,column=0,sticky="w",pady=7)
        self.reason=tk.Entry(f,font=("Arial",11),width=40); self.reason.grid(row=1,column=1,pady=7)
        tk.Label(f,text="This restores only quantities that have not already been returned by Credit Note.",
                 bg="white",fg="#555").grid(row=2,column=0,columnspan=2,sticky="w",pady=8)
        tk.Button(self,text="VOID SALE",bg="#c53030",fg="white",font=("Arial",12,"bold"),padx=20,pady=8,command=self.void).pack(pady=8)
        tk.Button(self,text="CANCEL",command=self.destroy,width=14).pack(pady=4)
    def void(self):
        try:sid=int(self.sid.get().strip())
        except ValueError:
            messagebox.showerror("Void","Enter a valid invoice number.",parent=self); return
        reason=self.reason.get().strip() or "Sale voided"
        actor=getattr(self.parent,"cashier_username","Unknown")
        actor_ctx={"username": actor, "role": getattr(self.parent,"cashier_role",""),
                   "is_admin": getattr(self.parent,"is_admin",False),
                   "can_void_sales": getattr(self.parent,"permissions",{}).get("can_void_sales",False),
                   "branch_id": getattr(self.parent,"current_branch_id",1)}
        from security_controls import require_permission
        try:
            require_permission(actor_ctx, "can_void_sales")
        except PermissionError as exc:
            messagebox.showerror("Permission Denied", str(exc), parent=self); return
        c=db()
        try:
            c.execute("BEGIN IMMEDIATE")
            from services.financial_service import void_sale
            result=void_sale(c, sid, actor=actor, reason=reason)
            c.commit()
            messagebox.showinfo("Sale Voided",
                f"Invoice #{sid:03d} has been voided.\n\n"
                "Unreturned stock quantities were restored.\n"
                "The sale is excluded from net sales and payment reconciliation.",parent=self)
            self.destroy()
        except Exception as exc:
            c.rollback(); messagebox.showerror("Void Failed",str(exc),parent=self)
        finally:c.close()

def install(app_cls):
    if getattr(app_cls,"_financial_controls_installed",False): return app_cls
    ensure_schema()
    old_menu=getattr(app_cls,"create_menu_bar",None)
    if not old_menu:return app_cls
    def menu(self):
        old_menu(self)
        try:
            mb=self.nametowidget(self["menu"])
            util=None
            for i in range(mb.index("end")+1):
                try:
                    if mb.type(i)=="cascade" and mb.entrycget(i,"label")=="Utility":
                        util=mb.nametowidget(mb.entrycget(i,"menu")); break
                except Exception as exc:
                    _bkpos_logger.warning("Suppressed exception in financial_controls.py", exc_info=exc)
            if util is not None:
                util.add_separator()
                util.add_command(label="Financial & Stock Control Center",command=lambda:FinancialControlCenter(self))
                util.add_command(label="Professional Cash-Up / Reconciliation",command=lambda:CashUpWindow(self))
                util.add_command(label="Stock Reconciliation",command=lambda:StockReconciliationWindow(self))
                util.add_command(label="Invoice Lifecycle",command=lambda:InvoiceLifecycleWindow(self))
                if getattr(self,"is_admin",False):
                    util.add_command(label="Void Completed Sale",command=lambda:VoidSaleWindow(self))
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in financial_controls.py", exc_info=exc)
    app_cls.create_menu_bar=menu
    app_cls._financial_controls_installed=True
    return app_cls
