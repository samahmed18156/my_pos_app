"""BKPOS Phase 17 — end-of-day and end-of-period operations control center."""
import csv
import sqlite3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, timedelta
from core.config import DB_PATH
from services.financial_reconciliation import financial_summary
from services.day_end_procedure import create_verified_day_end_backup

from ui.window_polish import polish_window
def _exists(conn, table):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None

def close_readiness(conn, date, branch_id=None):
    checks=[]
    def add(name, ok, detail): checks.append((name, "PASS" if ok else "REVIEW", detail))
    if _exists(conn,'cashier_shifts'):
        q="SELECT COUNT(*) FROM cashier_shifts WHERE date(opened_at)=? AND status='OPEN'"; n=conn.execute(q,(date,)).fetchone()[0]
        add("Cashier shifts", n==0, "No open shifts" if n==0 else f"{n} open shift(s) remain")
    else: add("Cashier shifts", False, "Cashier-shift table unavailable")
    if _exists(conn,'cashup_records'):
        n=conn.execute("SELECT COUNT(*) FROM cashup_records WHERE cashup_date=?",(date,)).fetchone()[0]
        v=conn.execute("SELECT COUNT(*) FROM cashup_records WHERE cashup_date=? AND ABS(COALESCE(difference,0))>0.01",(date,)).fetchone()[0]
        add("Cash-up records", True, f"{n} cash-up record(s) recorded")
        add("Cash-up variance", v==0, "No variance" if v==0 else f"{v} cash-up variance(s)")
    else: add("Cash-up records", False, "Cash-up table unavailable")
    if _exists(conn,'sales_history'):
        n=conn.execute("SELECT COUNT(*) FROM sales_history WHERE date(timestamp)=? AND COALESCE(status,'COMPLETED')<>'COMPLETED'",(date,)).fetchone()[0]
        add("Sales completion", n==0, "All sales completed" if n==0 else f"{n} incomplete sale(s)")
    if _exists(conn,'products'):
        n=conn.execute("SELECT COUNT(*) FROM products WHERE COALESCE(soh,0)<0").fetchone()[0]
        add("Stock integrity", n==0, "No negative stock" if n==0 else f"{n} product(s) have negative stock")
    if _exists(conn,'staged_conflicts'):
        n=conn.execute("SELECT COUNT(*) FROM staged_conflicts").fetchone()[0]
        add("Branch synchronization", n==0, "No staged conflicts" if n==0 else f"{n} staged conflict(s)")
    return checks

def period_summary(conn, start_date, end_date, branch_id=None):
    s=financial_summary(conn,start_date=start_date,end_date=end_date,branch_id=branch_id)
    if _exists(conn,'cashier_shifts'):
        open_shifts=conn.execute("SELECT COUNT(*) FROM cashier_shifts WHERE status='OPEN' AND date(opened_at)<=?",(end_date,)).fetchone()[0]
    else: open_shifts=0
    if _exists(conn,'cashup_records'):
        variances=conn.execute("SELECT COUNT(*) FROM cashup_records WHERE cashup_date BETWEEN ? AND ? AND ABS(COALESCE(difference,0))>0.01",(start_date,end_date)).fetchone()[0]
    else: variances=0
    return {"sales":s["gross_sales"],"returns":s["returns"],"net_sales":s["net_sales"],"expenses":s["expenses"],"profit":s["net_profit"],"transactions":s["transactions"],"open_shifts":int(open_shifts),"cash_variances":int(variances)}

class EndOfDayOperationsWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); polish_window(self); self.parent=parent
        self.title("BKPOS End-of-Day & Period Operations"); self.geometry("1260x780"); self.configure(bg="#eef2f7"); self.transient(parent); self.grab_set(); self._build(); self._set_period(1); self.refresh()
    def _build(self):
        tk.Label(self,text="END-OF-DAY / END-OF-PERIOD OPERATIONS",font=("Segoe UI",19,"bold"),bg="#2c5282",fg="white",pady=13).pack(fill="x")
        bar=tk.Frame(self,bg="#eef2f7",pady=9); bar.pack(fill="x",padx=15)
        tk.Label(bar,text="From",bg="#eef2f7").pack(side="left"); self.frm=tk.Entry(bar,width=12); self.frm.pack(side="left",padx=4)
        tk.Label(bar,text="To",bg="#eef2f7").pack(side="left"); self.to=tk.Entry(bar,width=12); self.to.pack(side="left",padx=4)
        for d,label in ((1,"Today"),(7,"7 Days"),(30,"30 Days"),(90,"90 Days")): tk.Button(bar,text=label,command=lambda x=d:self._set_period(x)).pack(side="left",padx=3)
        tk.Button(bar,text="RUN CLOSE REVIEW",font=("Segoe UI",10,"bold"),command=self.refresh).pack(side="left",padx=8); tk.Button(bar,text="VERIFIED DAY-END BACKUP",command=self.create_day_end_backup).pack(side="left",padx=3); tk.Button(bar,text="EXPORT CSV",command=self.export_csv).pack(side="left",padx=3)
        self.status=tk.Label(bar,text="",bg="#eef2f7"); self.status.pack(side="left",padx=10)
        cards=tk.Frame(self,bg="#eef2f7"); cards.pack(fill="x",padx=15,pady=4); self.cards={}
        for i,k in enumerate(("Net Sales","Net Profit","Transactions","Open Shifts","Cash Variances","Close Checks")):
            f=tk.Frame(cards,bg="white",bd=1,relief="solid"); f.grid(row=0,column=i,padx=4,sticky="nsew"); cards.grid_columnconfigure(i,weight=1); tk.Label(f,text=k,bg="white",font=("Segoe UI",9,"bold")).pack(pady=(8,2)); v=tk.Label(f,text="—",bg="white",font=("Segoe UI",14,"bold")); v.pack(pady=(0,9)); self.cards[k]=v
        nb=ttk.Notebook(self); nb.pack(fill="both",expand=True,padx=15,pady=10); ptab=tk.Frame(nb,bg="white"); ctab=tk.Frame(nb,bg="white"); nb.add(ptab,text="Period Summary"); nb.add(ctab,text="Close Readiness")
        self.period_tree=self._tree(ptab,("metric","value")); self.check_tree=self._tree(ctab,("check","status","detail"))
    def _tree(self,parent,cols):
        t=ttk.Treeview(parent,columns=[x[0] for x in cols],show="headings")
        for key,h in cols: t.heading(key,text=h); t.column(key,width=300 if key!='detail' else 720,anchor="w")
        t.pack(fill="both",expand=True,padx=8,pady=8); return t
    def _set_period(self,days):
        end=datetime.now().date(); start=end-timedelta(days=days-1); self.frm.delete(0,'end'); self.frm.insert(0,start.isoformat()); self.to.delete(0,'end'); self.to.insert(0,end.isoformat())
    def _dates(self):
        a,b=self.frm.get().strip(),self.to.get().strip(); datetime.strptime(a,'%Y-%m-%d'); datetime.strptime(b,'%Y-%m-%d')
        if a>b: raise ValueError('From date cannot be after To date')
        return a,b
    def refresh(self):
        try:
            a,b=self._dates(); c=sqlite3.connect(DB_PATH,timeout=10); p=period_summary(c,a,b); checks=close_readiness(c,b); c.close()
            vals={'Net Sales':f"R {p['net_sales']:,.2f}",'Net Profit':f"R {p['profit']:,.2f}",'Transactions':p['transactions'],'Open Shifts':p['open_shifts'],'Cash Variances':p['cash_variances'],'Close Checks':f"{sum(x[1]=='PASS' for x in checks)}/{len(checks)}"}
            for k,v in vals.items(): self.cards[k].config(text=str(v))
            self.period_tree.delete(*self.period_tree.get_children())
            for k,v in (("Gross Sales",p['sales']),("Returns",p['returns']),("Net Sales",p['net_sales']),("Expenses",p['expenses']),("Net Profit",p['profit']),('Transactions',p['transactions']),('Open Shifts',p['open_shifts']),('Cash Variances',p['cash_variances'])): self.period_tree.insert('','end',values=(k,f"R {v:,.2f}" if isinstance(v,float) else v))
            self.check_tree.delete(*self.check_tree.get_children())
            for r in checks: self.check_tree.insert('','end',values=r)
            passed=sum(x[1]=='PASS' for x in checks); self.status.config(text=f"Review: {a} to {b} | {'READY TO CLOSE' if passed==len(checks) else 'REVIEW REQUIRED'} | Read-only")
        except Exception as e: messagebox.showerror('End-of-Day Operations',str(e),parent=self)
    def create_day_end_backup(self):
        try:
            result = create_verified_day_end_backup(DB_PATH)
            if result.get("ok"):
                messagebox.showinfo("Day-End Backup", f"Verified day-end backup created successfully:\n{result['path']}", parent=self)
            else:
                messagebox.showerror("Day-End Backup", result.get("error", "Backup verification failed."), parent=self)
        except Exception as e:
            messagebox.showerror("Day-End Backup", str(e), parent=self)

    def export_csv(self):
        try:a,b=self._dates()
        except Exception as e: messagebox.showerror('Invalid dates',str(e),parent=self); return
        pth=filedialog.asksaveasfilename(parent=self,defaultextension='.csv',filetypes=(('CSV files','*.csv'),),initialfile=f'end_of_day_{b}.csv')
        if not pth:return
        c=sqlite3.connect(DB_PATH,timeout=10); p=period_summary(c,a,b); checks=close_readiness(c,b); c.close()
        with open(pth,'w',newline='',encoding='utf-8-sig') as f:
            w=csv.writer(f); w.writerow(['BKPOS End-of-Day / Period Operations',a,b]); w.writerow(['Metric','Value']);
            for k,v in p.items(): w.writerow([k,v])
            w.writerow([]); w.writerow(['Close Check','Status','Detail']); w.writerows(checks)
        messagebox.showinfo('Export complete','CSV exported successfully.',parent=self)
