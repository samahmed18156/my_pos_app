import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from core.config import DB_PATH
from ui.window_polish import polish_window
DB_NAME=DB_PATH; BG="#eef2f7"; NAVY="#1f3f68"; GREEN="#2f855a"; WHITE="white"
def conn(): return sqlite3.connect(DB_NAME)
def ensure_creditor_payment_schema():
    c=conn()
    try:
        c.execute("""CREATE TABLE IF NOT EXISTS supplier_payments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,supplier_id INTEGER NOT NULL,
        supplier_account_no TEXT,supplier_name TEXT NOT NULL,
        payment_date DATETIME DEFAULT CURRENT_TIMESTAMP,amount REAL NOT NULL,
        payment_method TEXT NOT NULL DEFAULT 'Bank Transfer',reference TEXT,
        notes TEXT,cashier TEXT DEFAULT 'Unknown')""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_supplier_payments_supplier ON supplier_payments(supplier_id)")
        c.commit()
    finally:c.close()
class SupplierPaymentsWindow(tk.Toplevel):
    def __init__(self,parent,supplier_id=None):
        super().__init__(parent); polish_window(self); self.parent=parent; self.selected_supplier=supplier_id
        self.title("Supplier Payments & Creditor Settlement"); self.geometry("1180x760"); self.configure(bg=BG); self.transient(parent)
        ensure_creditor_payment_schema(); self.build(); self.load_suppliers()
        if supplier_id:self.select_supplier_id(supplier_id)
        self.refresh(); self.after(100,lambda:self.amount.focus_set()); self.bind("<Escape>",lambda e:self.destroy())
    def build(self):
        h=tk.Frame(self,bg=NAVY);h.pack(fill="x")
        tk.Label(h,text="SUPPLIER PAYMENTS & CREDITOR SETTLEMENT",font=("Arial",19,"bold"),bg=NAVY,fg=WHITE).pack(pady=(12,2))
        tk.Label(h,text="Record payments made to suppliers and track purchases, payments and outstanding balances.",font=("Arial",10),bg=NAVY,fg=WHITE).pack(pady=(0,12))
        body=tk.Frame(self,bg=BG);body.pack(fill="both",expand=True,padx=12,pady=12)
        left=tk.Frame(body,bg=WHITE,bd=1,relief="solid",width=350);left.pack(side="left",fill="y",padx=(0,10));left.pack_propagate(False)
        tk.Label(left,text="SUPPLIER",font=("Arial",13,"bold"),bg=WHITE,fg=NAVY).pack(anchor="w",padx=12,pady=(12,5))
        self.supplier_search=tk.Entry(left,font=("Arial",11));self.supplier_search.pack(fill="x",padx=12,pady=5);self.supplier_search.bind("<KeyRelease>",lambda e:self.load_suppliers())
        self.supplier_tree=ttk.Treeview(left,columns=("account","name"),show="headings");self.supplier_tree.heading("account",text="Account");self.supplier_tree.heading("name",text="Supplier");self.supplier_tree.column("account",width=120);self.supplier_tree.column("name",width=190);self.supplier_tree.pack(fill="both",expand=True,padx=12,pady=8);self.supplier_tree.bind("<<TreeviewSelect>>",self.on_supplier)
        right=tk.Frame(body,bg=WHITE,bd=1,relief="solid");right.pack(side="left",fill="both",expand=True)
        self.supplier_label=tk.Label(right,text="Select a supplier",font=("Arial",14,"bold"),bg=WHITE,fg=NAVY,anchor="w");self.supplier_label.pack(fill="x",padx=15,pady=(12,5))
        self.balance=tk.Label(right,text="Purchases: R 0.00    Payments: R 0.00    Outstanding: R 0.00",font=("Arial",11,"bold"),bg="#edf2f7",fg="#334155",anchor="w",padx=10,pady=9);self.balance.pack(fill="x",padx=15)
        form=tk.Frame(right,bg=WHITE);form.pack(fill="x",padx=15,pady=7)
        labels=[("Payment Amount (R) *",0,0),("Payment Method",0,2),("Reference",1,0),("Payment Date",1,2),("Notes",2,0)]
        for text,r,c in labels:tk.Label(form,text=text,font=("Arial",10,"bold"),bg=WHITE).grid(row=r,column=c,sticky="w",padx=4,pady=6)
        self.amount=tk.Entry(form,font=("Arial",11));self.amount.grid(row=0,column=1,sticky="ew",padx=6,pady=6)
        self.method=ttk.Combobox(form,values=["Cash","Card","Bank Transfer","Other"],state="readonly");self.method.set("Bank Transfer");self.method.grid(row=0,column=3,sticky="ew",padx=6,pady=6)
        self.reference=tk.Entry(form,font=("Arial",11));self.reference.grid(row=1,column=1,sticky="ew",padx=6,pady=6)
        self.date=tk.Entry(form,font=("Arial",11));self.date.insert(0,datetime.now().strftime("%Y-%m-%d"));self.date.grid(row=1,column=3,sticky="ew",padx=6,pady=6)
        self.notes=tk.Entry(form,font=("Arial",11));self.notes.grid(row=2,column=1,columnspan=3,sticky="ew",padx=6,pady=6)
        form.grid_columnconfigure(1,weight=1);form.grid_columnconfigure(3,weight=1)
        b=tk.Frame(right,bg=WHITE);b.pack(fill="x",padx=15,pady=5);tk.Button(b,text="RECORD PAYMENT",command=self.record_payment,bg=GREEN,fg=WHITE,font=("Arial",11,"bold"),width=20,height=2).pack(side="left",padx=4);tk.Button(b,text="CLEAR",command=self.clear_form,bg="#718096",fg=WHITE,font=("Arial",11,"bold"),width=12,height=2).pack(side="left",padx=4);tk.Button(b,text="CLOSE  ESC",command=self.destroy,bg=NAVY,fg=WHITE,font=("Arial",11,"bold"),width=14,height=2).pack(side="right",padx=4)
        tk.Label(right,text="PAYMENT HISTORY",font=("Arial",11,"bold"),bg=WHITE,fg=NAVY,anchor="w").pack(fill="x",padx=15,pady=(5,3))
        tf=tk.Frame(right,bg=WHITE);tf.pack(fill="both",expand=True,padx=15,pady=(0,12))
        self.tree=ttk.Treeview(tf,columns=("date","amount","method","reference","cashier","notes"),show="headings")
        for c,t,w in [("date","Date",120),("amount","Amount",110),("method","Method",130),("reference","Reference",140),("cashier","Cashier",110),("notes","Notes",230)]:self.tree.heading(c,text=t);self.tree.column(c,width=w,anchor="e" if c=="amount" else "w")
        self.tree.pack(fill="both",expand=True)
        tk.Label(self,text="Select supplier → enter amount → RECORD PAYMENT. Payments are stored permanently and reduce creditor balance.",bg="#dbe8f5",fg=NAVY,font=("Arial",10,"bold"),pady=7).pack(fill="x",side="bottom")
    def load_suppliers(self):
        q=self.supplier_search.get().strip(); self.supplier_tree.delete(*self.supplier_tree.get_children()); c=conn()
        try: rows=c.execute("SELECT id,supplier_account_no,name FROM accounts WHERE type='Supplier' AND (supplier_account_no LIKE ? OR name LIKE ? OR phone LIKE ?) ORDER BY name COLLATE NOCASE",(f"%{q}%",)*3).fetchall()
        finally:c.close()
        for r in rows:self.supplier_tree.insert("","end",iid=str(r[0]),values=(r[1] or "",r[2]))
        if self.selected_supplier and self.supplier_tree.exists(str(self.selected_supplier)):self.supplier_tree.selection_set(str(self.selected_supplier));self.supplier_tree.focus(str(self.selected_supplier))
    def select_supplier_id(self,sid):
        self.selected_supplier=sid
        if self.supplier_tree.exists(str(sid)):self.supplier_tree.selection_set(str(sid));self.supplier_tree.focus(str(sid));self.supplier_tree.see(str(sid))
    def on_supplier(self,event=None):
        sel=self.supplier_tree.selection()
        if sel:self.selected_supplier=int(sel[0]);self.refresh()
    def clear_form(self):
        self.amount.delete(0,"end");self.reference.delete(0,"end");self.notes.delete(0,"end");self.method.set("Bank Transfer");self.date.delete(0,"end");self.date.insert(0,datetime.now().strftime("%Y-%m-%d"));self.amount.focus_set()
    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        if not self.selected_supplier:self.supplier_label.config(text="Select a supplier");self.balance.config(text="Purchases: R 0.00    Payments: R 0.00    Outstanding: R 0.00");return
        c=conn()
        try:
            sup=c.execute("SELECT supplier_account_no,name FROM accounts WHERE id=? AND type='Supplier'",(self.selected_supplier,)).fetchone()
            if not sup:return
            purchases=float(c.execute("SELECT COALESCE(SUM(total_amount),0) FROM account_transactions WHERE account_id=? AND txn_type='PURCHASE'",(self.selected_supplier,)).fetchone()[0] or 0)
            grn=float(c.execute("SELECT COALESCE(SUM(total),0) FROM grn_headers WHERE supplier_account=? OR supplier_name=?",(sup[0],sup[1])).fetchone()[0] or 0); purchases=max(purchases,grn)
            payments=float(c.execute("SELECT COALESCE(SUM(total_amount),0) FROM account_transactions WHERE account_id=? AND txn_type='PAYMENT'",(self.selected_supplier,)).fetchone()[0] or 0)
            self.supplier_label.config(text=f"{sup[1]}   •   {sup[0]}");self.balance.config(text=f"Purchases: R {purchases:,.2f}    Payments: R {payments:,.2f}    Outstanding: R {purchases-payments:,.2f}")
            rows=c.execute("SELECT payment_date,amount,payment_method,reference,cashier,notes FROM supplier_payments WHERE supplier_id=? ORDER BY id DESC",(self.selected_supplier,)).fetchall()
            for r in rows:self.tree.insert("","end",values=(r[0],f"R {float(r[1]):,.2f}",r[2],r[3] or "",r[4] or "",r[5] or ""))
        finally:c.close()
    def record_payment(self):
        if not self.selected_supplier:messagebox.showwarning("Supplier Payment","Select a supplier first.",parent=self);return
        try:a=float(self.amount.get().replace(",","").strip())
        except ValueError:messagebox.showerror("Supplier Payment","Enter a valid payment amount.",parent=self);return
        if a<=0:messagebox.showwarning("Supplier Payment","Payment amount must be greater than zero.",parent=self);return
        c=conn()
        try:
            sup=c.execute("SELECT supplier_account_no,name FROM accounts WHERE id=? AND type='Supplier'",(self.selected_supplier,)).fetchone()
            purchases=float(c.execute("SELECT COALESCE(SUM(total_amount),0) FROM account_transactions WHERE account_id=? AND txn_type='PURCHASE'",(self.selected_supplier,)).fetchone()[0] or 0);grn=float(c.execute("SELECT COALESCE(SUM(total),0) FROM grn_headers WHERE supplier_account=? OR supplier_name=?",(sup[0],sup[1])).fetchone()[0] or 0);purchases=max(purchases,grn)
            payments=float(c.execute("SELECT COALESCE(SUM(total_amount),0) FROM account_transactions WHERE account_id=? AND txn_type='PAYMENT'",(self.selected_supplier,)).fetchone()[0] or 0);outstanding=purchases-payments
            if a>max(outstanding,0)+.005 and not messagebox.askyesno("Overpayment","This exceeds the current outstanding balance. Record it as an advance/credit?",parent=self):return
            dt=self.date.get().strip() or datetime.now().strftime("%Y-%m-%d")
            c.execute("INSERT INTO supplier_payments(supplier_id,supplier_account_no,supplier_name,payment_date,amount,payment_method,reference,notes,cashier) VALUES(?,?,?,?,?,?,?,?,?)",(self.selected_supplier,sup[0],sup[1],dt,a,self.method.get(),self.reference.get().strip(),self.notes.get().strip(),getattr(self.parent,"cashier_username","Unknown")))
            c.execute("INSERT INTO account_transactions(account_id,txn_type,total_amount,txn_date) VALUES(?,?,?,?)",(self.selected_supplier,"PAYMENT",a,dt))
            c.commit();messagebox.showinfo("Payment Recorded",f"Payment of R {a:,.2f} recorded for {sup[1]}.",parent=self);self.clear_form();self.refresh()
        except Exception as e:c.rollback();messagebox.showerror("Payment Error",str(e),parent=self)
        finally:c.close()
CreditorPaymentsWindow=SupplierPaymentsWindow
