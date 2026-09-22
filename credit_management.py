"""BKPOS Phase 14 — Customer & Supplier Credit Management.

Read-only management analytics. No balances, limits, payments, sales or supplier
transactions are posted or altered by this module.
"""
from __future__ import annotations
import csv
import sqlite3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, timedelta
from core.config import DB_PATH


def _money(v): return round(float(v or 0), 2)

def _conn():
    c = sqlite3.connect(DB_PATH, timeout=10); c.execute("PRAGMA foreign_keys=ON"); return c

def _exists(c, table):
    return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None

def _dates(as_of): datetime.strptime(as_of, "%Y-%m-%d")

def customer_credit(conn, as_of=None):
    as_of = as_of or datetime.now().date().isoformat(); _dates(as_of)
    if not _exists(conn, "customers"): return []
    rows = conn.execute("""SELECT id,name,COALESCE(phone,''),COALESCE(credit_limit,0),COALESCE(active,1)
        FROM customers ORDER BY name""").fetchall()
    out=[]
    for cid,name,phone,limit,active in rows:
        balance=float(conn.execute("SELECT COALESCE(SUM(debit-credit),0) FROM customer_account_transactions WHERE customer_id=? AND date(txn_date)<=date(?)",(cid,as_of)).fetchone()[0] or 0) if _exists(conn,"customer_account_transactions") else 0
        balance=max(0.0,balance); limit=float(limit or 0); available=max(0.0,limit-balance) if limit>0 else 0.0
        util=(balance/limit*100) if limit>0 else (100.0 if balance>0 else 0.0)
        invoices=int(conn.execute("SELECT COUNT(*) FROM customer_account_invoices WHERE customer_id=? AND outstanding>0.005 AND date(invoice_date)<=date(?)",(cid,as_of)).fetchone()[0] or 0) if _exists(conn,"customer_account_invoices") else 0
        overdue=float(conn.execute("SELECT COALESCE(SUM(outstanding),0) FROM customer_account_invoices WHERE customer_id=? AND outstanding>0.005 AND date(invoice_date)<=date(?) AND julianday(?) - julianday(invoice_date)>30",(cid,as_of,as_of)).fetchone()[0] or 0) if _exists(conn,"customer_account_invoices") else 0
        risk="NO LIMIT" if limit<=0 and balance<=0 else "OVER LIMIT" if limit>0 and balance>limit+0.01 else "HIGH" if util>=90 or overdue>0 else "WATCH" if util>=75 else "OK"
        out.append((int(cid),name or f"Customer #{cid}",phone,_money(balance),_money(limit),_money(available),round(util,1),invoices,_money(overdue),risk,bool(active)))
    return out

def customer_ageing_detail(conn, as_of=None):
    as_of=as_of or datetime.now().date().isoformat(); _dates(as_of)
    if not _exists(conn,"customer_account_invoices"): return []
    rows=conn.execute("""SELECT i.customer_id,COALESCE(c.name,'Customer #'||i.customer_id),i.invoice_no,i.invoice_date,
        COALESCE(i.total,0),COALESCE(i.paid,0),COALESCE(i.outstanding,0)
        FROM customer_account_invoices i LEFT JOIN customers c ON c.id=i.customer_id
        WHERE i.outstanding>0.005 AND date(i.invoice_date)<=date(?) ORDER BY i.invoice_date""",(as_of,)).fetchall()
    out=[]
    for cid,name,inv,dt,total,paid,outstanding in rows:
        try: age=max(0,(datetime.strptime(as_of,'%Y-%m-%d').date()-datetime.strptime(str(dt)[:10],'%Y-%m-%d').date()).days)
        except ValueError: age=0
        bucket='0-30' if age<=30 else '31-60' if age<=60 else '61-90' if age<=90 else '90+'
        out.append((cid,name,inv,str(dt),_money(total),_money(paid),_money(outstanding),age,bucket))
    return out

def supplier_credit(conn, as_of=None):
    as_of=as_of or datetime.now().date().isoformat(); _dates(as_of)
    if not _exists(conn,"accounts"): return []
    rows=conn.execute("SELECT id,COALESCE(name,'Supplier #'||id),COALESCE(supplier_account_no,''),COALESCE(credit_limit,0),COALESCE(payment_terms,''),COALESCE(active,1) FROM accounts WHERE lower(COALESCE(type,''))='supplier' ORDER BY name").fetchall()
    out=[]
    for sid,name,acct,limit,terms,active in rows:
        purchase=float(conn.execute("SELECT COALESCE(SUM(total_amount),0) FROM account_transactions WHERE account_id=? AND txn_type='PURCHASE' AND date(txn_date)<=date(?)",(sid,as_of)).fetchone()[0] or 0) if _exists(conn,"account_transactions") else 0
        payment=float(conn.execute("SELECT COALESCE(SUM(amount),0) FROM supplier_payments WHERE supplier_id=? AND date(payment_date)<=date(?)",(sid,as_of)).fetchone()[0] or 0) if _exists(conn,"supplier_payments") else 0
        credit=float(conn.execute("SELECT COALESCE(SUM(amount),0) FROM supplier_credits WHERE supplier_id=? AND date(credit_date)<=date(?)",(sid,as_of)).fetchone()[0] or 0) if _exists(conn,"supplier_credits") else 0
        balance=max(0.0,purchase-payment-credit); limit=float(limit or 0); util=(balance/limit*100) if limit>0 else 0
        risk='OVER LIMIT' if limit>0 and balance>limit+0.01 else 'HIGH' if limit>0 and util>=90 else 'WATCH' if limit>0 and util>=75 else 'OK'
        out.append((int(sid),name,acct,_money(purchase),_money(payment),_money(credit),_money(balance),_money(limit),round(util,1),terms,risk,bool(active)))
    return out

def supplier_ageing_detail(conn, as_of=None):
    as_of=as_of or datetime.now().date().isoformat(); _dates(as_of)
    if not _exists(conn,"grn_headers"): return []
    cols={r[1] for r in conn.execute("PRAGMA table_info(grn_headers)")}
    if not {'supplier_id','outstanding'}.issubset(cols): return []
    date_col='created_at' if 'created_at' in cols else ('date' if 'date' in cols else None)
    if not date_col:return []
    name_expr='COALESCE(g.supplier_name,\'Supplier #\'||g.supplier_id)' if 'supplier_name' in cols else "'Supplier #'||g.supplier_id"
    rows=conn.execute(f"SELECT g.supplier_id,{name_expr},g.{date_col},COALESCE(g.outstanding,0) FROM grn_headers g WHERE g.outstanding>0.005 AND date(g.{date_col})<=date(?) ORDER BY g.{date_col}",(as_of,)).fetchall()
    out=[]
    for sid,name,dt,amount in rows:
        try: age=max(0,(datetime.strptime(as_of,'%Y-%m-%d').date()-datetime.strptime(str(dt)[:10],'%Y-%m-%d').date()).days)
        except ValueError: age=0
        bucket='0-30' if age<=30 else '31-60' if age<=60 else '61-90' if age<=90 else '90+'
        out.append((sid,name,str(dt),_money(amount),age,bucket))
    return out

def credit_summary(conn, as_of=None):
    customers=customer_credit(conn,as_of); suppliers=supplier_credit(conn,as_of)
    return {'customers':len(customers),'customer_balance':_money(sum(r[3] for r in customers)),'customer_over_limit':sum(r[9]=='OVER LIMIT' for r in customers),'customer_overdue':_money(sum(r[8] for r in customers)), 'suppliers':len(suppliers),'supplier_balance':_money(sum(r[6] for r in suppliers)),'supplier_over_limit':sum(r[10]=='OVER LIMIT' for r in suppliers)}

class CreditManagementWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); self.parent=parent; self.title('BKPOS Customer & Supplier Credit Management'); self.geometry('1450x820'); self.configure(bg='#eef2f7'); self.transient(parent); self._build(); self._set_date(); self.refresh(); self.bind('<Escape>',lambda e:self.destroy())
    def _build(self):
        tk.Label(self,text='CUSTOMER & SUPPLIER CREDIT MANAGEMENT',font=('Segoe UI',19,'bold'),bg='#2c5282',fg='white',pady=13).pack(fill='x')
        bar=tk.Frame(self,bg='#eef2f7',pady=9); bar.pack(fill='x',padx=15)
        tk.Label(bar,text='As of',bg='#eef2f7',font=('Segoe UI',10,'bold')).pack(side='left'); self.dt=tk.Entry(bar,width=12); self.dt.pack(side='left',padx=5); tk.Button(bar,text='TODAY',command=self._set_date).pack(side='left',padx=3); tk.Button(bar,text='REFRESH',font=('Segoe UI',10,'bold'),command=self.refresh).pack(side='left',padx=8); tk.Button(bar,text='EXPORT CSV',command=self.export_csv).pack(side='left',padx=3); self.status=tk.Label(bar,text='',bg='#eef2f7'); self.status.pack(side='left',padx=10)
        cards=tk.Frame(self,bg='#eef2f7'); cards.pack(fill='x',padx=15,pady=3); self.cards={}
        for i,k in enumerate(('Customer Debt','Over-limit Customers','Overdue Debt','Supplier Creditors','Supplier Balance','Over-limit Suppliers')):
            f=tk.Frame(cards,bg='white',bd=1,relief='solid'); f.grid(row=0,column=i,padx=4,sticky='nsew'); cards.grid_columnconfigure(i,weight=1); tk.Label(f,text=k,bg='white',font=('Segoe UI',9,'bold')).pack(pady=(8,2)); v=tk.Label(f,text='—',bg='white',font=('Segoe UI',14,'bold')); v.pack(pady=(0,9)); self.cards[k]=v
        nb=ttk.Notebook(self); nb.pack(fill='both',expand=True,padx=15,pady=10)
        self.ctab=tk.Frame(nb,bg='white'); self.cage=tk.Frame(nb,bg='white'); self.stab=tk.Frame(nb,bg='white'); self.sage=tk.Frame(nb,bg='white')
        nb.add(self.ctab,text='Customer Credit'); nb.add(self.cage,text='Customer Ageing'); nb.add(self.stab,text='Supplier Credit'); nb.add(self.sage,text='Supplier Ageing')
        self.ctree=self._tree(self.ctab,('id','name','phone','balance','limit','available','util','invoices','overdue','risk','active'),('ID','Customer','Phone','Balance','Limit','Available','Util %','Open Invoices','Overdue >30d','Risk','Active'))
        self.cagetree=self._tree(self.cage,('id','customer','invoice','date','total','paid','outstanding','age','bucket'),('ID','Customer','Invoice','Invoice Date','Total','Paid','Outstanding','Age','Bucket'))
        self.stree=self._tree(self.stab,('id','supplier','account','purchases','payments','credits','balance','limit','util','terms','risk','active'),('ID','Supplier','Account','Purchases','Payments','Credits','Balance','Limit','Util %','Terms','Risk','Active'))
        self.sagetree=self._tree(self.sage,('id','supplier','date','outstanding','age','bucket'),('ID','Supplier','Invoice Date','Outstanding','Age','Bucket'))
    def _tree(self,parent,cols,heads):
        fr=tk.Frame(parent,bg='white'); fr.pack(fill='both',expand=True,padx=10,pady=10); t=ttk.Treeview(fr,columns=cols,show='headings');
        for c,h in zip(cols,heads): t.heading(c,text=h); t.column(c,width=105,anchor='e' if c in ('balance','limit','available','util','overdue','total','paid','outstanding','age','purchases','payments','credits') else 'w')
        sy=ttk.Scrollbar(fr,orient='vertical',command=t.yview); t.configure(yscrollcommand=sy.set); t.pack(side='left',fill='both',expand=True); sy.pack(side='right',fill='y'); return t
    def _set_date(self): self.dt.delete(0,'end'); self.dt.insert(0,datetime.now().date().isoformat())
    def refresh(self):
        try:
            as_of=self.dt.get().strip(); _dates(as_of); c=_conn()
            try: summary=credit_summary(c,as_of); cr=customer_credit(c,as_of); ca=customer_ageing_detail(c,as_of); sr=supplier_credit(c,as_of); sa=supplier_ageing_detail(c,as_of)
            finally:c.close()
            vals={'Customer Debt':f"R {summary['customer_balance']:,.2f}",'Over-limit Customers':summary['customer_over_limit'],'Overdue Debt':f"R {summary['customer_overdue']:,.2f}",'Supplier Creditors':summary['suppliers'],'Supplier Balance':f"R {summary['supplier_balance']:,.2f}",'Over-limit Suppliers':summary['supplier_over_limit']}
            for k,v in vals.items(): self.cards[k].config(text=str(v))
            for t in (self.ctree,self.cagetree,self.stree,self.sagetree): t.delete(*t.get_children())
            for r in cr:self.ctree.insert('','end',values=(*r[:9],r[9],'Yes' if r[10] else 'No'))
            for r in ca:self.cagetree.insert('','end',values=r)
            for r in sr:self.stree.insert('','end',values=(*r[:10],r[10],'Yes' if r[11] else 'No'))
            for r in sa:self.sagetree.insert('','end',values=r)
            self.status.config(text=f'As of {as_of} | Read-only | {summary["customers"]} customers / {summary["suppliers"]} suppliers')
        except Exception as e: messagebox.showerror('Credit Management',str(e),parent=self)
    def export_csv(self):
        try: as_of=self.dt.get().strip(); _dates(as_of); c=_conn();
        except Exception as e: messagebox.showerror('Credit Management',str(e),parent=self); return
        try: cr=customer_credit(c,as_of); ca=customer_ageing_detail(c,as_of); sr=supplier_credit(c,as_of); sa=supplier_ageing_detail(c,as_of)
        finally:c.close()
        p=filedialog.asksaveasfilename(parent=self,defaultextension='.csv',initialfile=f'credit_management_{as_of}.csv',filetypes=(('CSV files','*.csv'),));
        if not p:return
        try:
            with open(p,'w',newline='',encoding='utf-8-sig') as f:
                w=csv.writer(f); w.writerow(['BKPOS Credit Management',as_of]);
                for title,heads,rows in (('Customer Credit',self.ctree['columns'],cr),('Customer Ageing',self.cagetree['columns'],ca),('Supplier Credit',self.stree['columns'],sr),('Supplier Ageing',self.sagetree['columns'],sa)):
                    w.writerow([]); w.writerow([title]); w.writerow([t.heading(x,'text') for x in heads]);
                    for r in rows:w.writerow(r)
            messagebox.showinfo('Credit Management','CSV exported successfully.',parent=self)
        except Exception as e: messagebox.showerror('Export Failed',str(e),parent=self)
