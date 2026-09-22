"""BKPOS Phase 4 financial control dashboard (read-only)."""
import csv
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, timedelta
import sqlite3
from core.config import DB_PATH
from services.financial_controls_service import payment_reconciliation, cashup_exceptions, customer_ageing, supplier_ageing, financial_exceptions

class FinancialControlsWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); self.parent=parent
        self.title("BKPOS Advanced Financial Controls"); self.geometry("1250x780"); self.minsize(1080,650); self.configure(bg="#eef2f7")
        self._build(); self._set_period(30); self.refresh()
    def _build(self):
        tk.Label(self,text="ADVANCED FINANCIAL & MANAGEMENT CONTROLS",font=("Segoe UI",19,"bold"),bg="#2c5282",fg="white",pady=13).pack(fill="x")
        bar=tk.Frame(self,bg="#eef2f7",pady=9); bar.pack(fill="x",padx=15)
        tk.Label(bar,text="From",bg="#eef2f7").pack(side="left"); self.frm=tk.Entry(bar,width=12); self.frm.pack(side="left",padx=4)
        tk.Label(bar,text="To",bg="#eef2f7").pack(side="left"); self.to=tk.Entry(bar,width=12); self.to.pack(side="left",padx=4)
        for d,label in ((1,"Today"),(7,"7 Days"),(30,"30 Days"),(90,"90 Days")): tk.Button(bar,text=label,command=lambda x=d:self._set_period(x)).pack(side="left",padx=3)
        tk.Button(bar,text="RUN CONTROLS",font=("Segoe UI",10,"bold"),command=self.refresh).pack(side="left",padx=8)
        tk.Button(bar,text="EXPORT CSV",command=self.export_csv).pack(side="left",padx=3)
        self.status=tk.Label(bar,text="",bg="#eef2f7"); self.status.pack(side="left",padx=10)
        cards=tk.Frame(self,bg="#eef2f7"); cards.pack(fill="x",padx=15,pady=4); self.cards={}
        for i,k in enumerate(("Net Sales","Payment Difference","Cash Variances","Debtors","Creditors","Exceptions")):
            f=tk.Frame(cards,bg="white",bd=1,relief="solid"); f.grid(row=0,column=i,padx=4,sticky="nsew"); cards.grid_columnconfigure(i,weight=1)
            tk.Label(f,text=k,bg="white",font=("Segoe UI",9,"bold")).pack(pady=(8,2)); v=tk.Label(f,text="—",bg="white",font=("Segoe UI",13,"bold")); v.pack(pady=(0,9)); self.cards[k]=v
        nb=ttk.Notebook(self); nb.pack(fill="both",expand=True,padx=15,pady=10)
        self.exc=self._tab(nb,"Exceptions",("type","detail","amount","status"),(120,600,140,120),("Type","Exception","Amount","Status"))
        self.debt=self._tab(nb,"Debtor Ageing",("customer","invoice","amount","age","bucket"),(280,160,140,90,100),("Customer","Invoice Date","Outstanding","Days","Bucket"))
        self.cred=self._tab(nb,"Creditor Ageing",("supplier","invoice","amount","age","bucket"),(280,160,140,90,100),("Supplier","Invoice Date","Outstanding","Days","Bucket"))
        self.cash=self._tab(nb,"Cash-Up",("cashier","expected","actual","difference","status"),(180,160,160,160,120),("Cashier","Expected","Actual","Difference","Status"))
    def _tab(self,nb,title,cols,widths,heads):
        fr=tk.Frame(nb,bg="white"); nb.add(fr,text=title); tree=ttk.Treeview(fr,columns=cols,show="headings")
        for c,w,h in zip(cols,widths,heads): tree.heading(c,text=h); tree.column(c,width=w,anchor="e" if c in ("amount","expected","actual","difference") else "w")
        tree.pack(fill="both",expand=True,padx=8,pady=8); return tree
    def _set_period(self,days):
        end=datetime.now().date(); start=end-timedelta(days=days-1)
        self.frm.delete(0,"end"); self.frm.insert(0,start.isoformat()); self.to.delete(0,"end"); self.to.insert(0,end.isoformat())
    def refresh(self):
        try:
            a,b=self.frm.get().strip(),self.to.get().strip(); datetime.strptime(a,"%Y-%m-%d"); datetime.strptime(b,"%Y-%m-%d")
            if a>b: raise ValueError("From date cannot be after To date")
            c=sqlite3.connect(DB_PATH,timeout=10); recon=payment_reconciliation(c,start_date=a,end_date=b); cash=cashup_exceptions(c,date=b); debt=customer_ageing(c,as_of=b); cred=supplier_ageing(c,as_of=b); exc=financial_exceptions(c,start_date=a,end_date=b); c.close()
            self.cards["Net Sales"].config(text=f"R {recon['sales']:,.2f}"); self.cards["Payment Difference"].config(text=f"R {recon['difference']:,.2f}"); self.cards["Cash Variances"].config(text=f"{sum(1 for x in cash if x['status']!='OK'):,}"); self.cards["Debtors"].config(text=f"R {sum(x[3] for x in debt):,.2f}"); self.cards["Creditors"].config(text=f"R {sum(x[3] for x in cred):,.2f}"); self.cards["Exceptions"].config(text=f"{len(exc):,}")
            for t in (self.exc,self.debt,self.cred,self.cash): t.delete(*t.get_children())
            for typ,detail,amount in exc: self.exc.insert("","end",values=(typ,detail,f"R {amount:,.2f}","REVIEW"))
            for _,name,stamp,amt,age,bucket in debt: self.debt.insert("","end",values=(name,stamp,f"R {amt:,.2f}",age,bucket))
            for _,name,stamp,amt,age,bucket in cred: self.cred.insert("","end",values=(name,stamp,f"R {amt:,.2f}",age,bucket))
            for r in cash: self.cash.insert("","end",values=(r['cashier'],f"R {r['expected_cash']:,.2f}",f"R {r['actual_cash']:,.2f}",f"R {r['difference']:,.2f}",r['status']))
            self.status.config(text=f"Controls: {a} to {b} | Payment reconciliation: {recon['status']}")
        except Exception as e: messagebox.showerror("Financial Controls",str(e),parent=self)
    def export_csv(self):
        p=filedialog.asksaveasfilename(parent=self,defaultextension=".csv",filetypes=(("CSV files","*.csv"),),initialfile=f"financial_controls_{self.to.get()}.csv")
        if not p:return
        try:
            c=sqlite3.connect(DB_PATH,timeout=10); exc=financial_exceptions(c,start_date=self.frm.get().strip(),end_date=self.to.get().strip()); c.close()
            with open(p,"w",newline="",encoding="utf-8") as f:
                w=csv.writer(f); w.writerow(["Type","Exception","Amount","Status"]); w.writerows((*x,"REVIEW") for x in exc)
            messagebox.showinfo("Financial Controls","CSV exported successfully.",parent=self)
        except Exception as e: messagebox.showerror("Export",str(e),parent=self)
