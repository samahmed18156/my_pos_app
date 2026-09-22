"""BKPOS Phase 12 — Audit, compliance and exception monitoring.

Read-only management controls. Existing posting and operational workflows are
not changed; this module consolidates signals already present in BKPOS.
"""
import csv
import sqlite3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, timedelta
from core.config import DB_PATH


def _exists(conn, table):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def audit_activity(conn, start_date, end_date):
    if not _exists(conn, "audit_log"):
        return {"events": 0, "users": 0, "failed_logins": 0, "void_events": 0}
    rows = conn.execute("""SELECT COUNT(*), COUNT(DISTINCT username),
        SUM(CASE WHEN event_type='LOGIN_FAILED' THEN 1 ELSE 0 END),
        SUM(CASE WHEN event_type IN ('SALE_VOIDED','VOID_SALE') OR event_type LIKE '%VOID%' THEN 1 ELSE 0 END)
        FROM audit_log WHERE date(event_time) BETWEEN ? AND ?""", (start_date, end_date)).fetchone()
    return {"events": int(rows[0] or 0), "users": int(rows[1] or 0), "failed_logins": int(rows[2] or 0), "void_events": int(rows[3] or 0)}


def compliance_exceptions(conn, start_date, end_date, tolerance=0.01):
    """Return standardized exception tuples: category, severity, detail, amount."""
    out = []
    if _exists(conn, "cashier_shifts"):
        rows = conn.execute("SELECT id,cashier,status,COALESCE(difference,0) FROM cashier_shifts WHERE date(opened_at) BETWEEN ? AND ?", (start_date,end_date)).fetchall()
        for sid,cashier,status,diff in rows:
            if status == 'OPEN': out.append(("Shift", "HIGH", f"Open shift #{sid} — {cashier}", 0.0))
            elif abs(float(diff or 0)) > tolerance: out.append(("Cash", "HIGH", f"Shift #{sid} — cash variance for {cashier}", float(diff or 0)))
    if _exists(conn, "sales_history"):
        rows = conn.execute("SELECT COUNT(*), COALESCE(SUM(total_amount),0) FROM sales_history WHERE date(timestamp) BETWEEN ? AND ? AND COALESCE(voided,0)=1", (start_date,end_date)).fetchone()
        if rows[0]: out.append(("Sales", "MEDIUM", f"{rows[0]} voided sale(s)", float(rows[1] or 0)))
    if _exists(conn, "return_history"):
        n,amt=conn.execute("SELECT COUNT(*),COALESCE(SUM(total_amount),0) FROM return_history WHERE date(timestamp) BETWEEN ? AND ?",(start_date,end_date)).fetchone()
        if n: out.append(("Returns", "MEDIUM", f"{n} return(s) processed", float(amt or 0)))
    if _exists(conn, "products"):
        n=conn.execute("SELECT COUNT(*) FROM products WHERE COALESCE(soh,0)<0").fetchone()[0]
        if n: out.append(("Stock", "HIGH", f"{n} product(s) with negative stock", 0.0))
    if _exists(conn, "staged_conflicts"):
        n=conn.execute("SELECT COUNT(*) FROM staged_conflicts").fetchone()[0]
        if n: out.append(("Sync", "HIGH", f"{n} staged branch conflict(s) awaiting review", 0.0))
    if _exists(conn, "audit_log"):
        n=conn.execute("SELECT COUNT(*) FROM audit_log WHERE date(event_time) BETWEEN ? AND ? AND event_type='LOGIN_FAILED'",(start_date,end_date)).fetchone()[0]
        if n: out.append(("Security", "MEDIUM", f"{n} failed login event(s)", 0.0))
    return out


def compliance_summary(conn, start_date, end_date):
    ex = compliance_exceptions(conn,start_date,end_date)
    high=sum(1 for x in ex if x[1]=='HIGH'); medium=sum(1 for x in ex if x[1]=='MEDIUM')
    score=max(0,100-(high*15)-(medium*5))
    activity=audit_activity(conn,start_date,end_date)
    return {"score":score,"high":high,"medium":medium,"total":len(ex),**activity}


class ComplianceControlWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); self.parent=parent
        self.title("BKPOS Audit & Compliance Center"); self.geometry("1220x760"); self.configure(bg="#eef2f7"); self.transient(parent); self.grab_set()
        self._build(); self._set_period(30); self.refresh()
    def _build(self):
        tk.Label(self,text="AUDIT & COMPLIANCE CENTER",font=("Segoe UI",19,"bold"),bg="#2c5282",fg="white",pady=13).pack(fill="x")
        bar=tk.Frame(self,bg="#eef2f7",pady=9); bar.pack(fill="x",padx=15)
        tk.Label(bar,text="From",bg="#eef2f7").pack(side="left"); self.frm=tk.Entry(bar,width=12); self.frm.pack(side="left",padx=4)
        tk.Label(bar,text="To",bg="#eef2f7").pack(side="left"); self.to=tk.Entry(bar,width=12); self.to.pack(side="left",padx=4)
        for d,label in ((1,"Today"),(7,"7 Days"),(30,"30 Days"),(90,"90 Days")): tk.Button(bar,text=label,command=lambda x=d:self._set_period(x)).pack(side="left",padx=3)
        tk.Button(bar,text="RUN REVIEW",font=("Segoe UI",10,"bold"),command=self.refresh).pack(side="left",padx=8)
        tk.Button(bar,text="EXPORT CSV",command=self.export_csv).pack(side="left",padx=3)
        self.status=tk.Label(bar,text="",bg="#eef2f7"); self.status.pack(side="left",padx=10)
        cards=tk.Frame(self,bg="#eef2f7"); cards.pack(fill="x",padx=15,pady=4); self.cards={}
        for i,k in enumerate(("Compliance Score","High Risk","Medium Risk","Exceptions","Audit Events","Failed Logins")):
            f=tk.Frame(cards,bg="white",bd=1,relief="solid"); f.grid(row=0,column=i,padx=4,sticky="nsew"); cards.grid_columnconfigure(i,weight=1)
            tk.Label(f,text=k,bg="white",font=("Segoe UI",9,"bold")).pack(pady=(8,2)); v=tk.Label(f,text="—",bg="white",font=("Segoe UI",14,"bold")); v.pack(pady=(0,9)); self.cards[k]=v
        fr=tk.Frame(self,bg="white"); fr.pack(fill="both",expand=True,padx=15,pady=10)
        self.tree=ttk.Treeview(fr,columns=("category","severity","detail","amount"),show="headings")
        for c,h,w in (("category","Category",130),("severity","Severity",110),("detail","Exception / Finding",700),("amount","Amount",150)):
            self.tree.heading(c,text=h); self.tree.column(c,width=w,anchor="e" if c=="amount" else "w")
        self.tree.pack(fill="both",expand=True,padx=8,pady=8)
    def _set_period(self,days):
        end=datetime.now().date(); start=end-timedelta(days=days-1)
        self.frm.delete(0,"end"); self.frm.insert(0,start.isoformat()); self.to.delete(0,"end"); self.to.insert(0,end.isoformat())
    def _dates(self):
        a,b=self.frm.get().strip(),self.to.get().strip(); datetime.strptime(a,"%Y-%m-%d"); datetime.strptime(b,"%Y-%m-%d")
        if a>b: raise ValueError("From date cannot be after To date")
        return a,b
    def refresh(self):
        try:
            a,b=self._dates(); c=sqlite3.connect(DB_PATH,timeout=10); s=compliance_summary(c,a,b); ex=compliance_exceptions(c,a,b); c.close()
            for k,val in (("Compliance Score",f"{s['score']}%"),("High Risk",s['high']),("Medium Risk",s['medium']),("Exceptions",s['total']),("Audit Events",s['events']),("Failed Logins",s['failed_logins'])): self.cards[k].config(text=str(val))
            self.tree.delete(*self.tree.get_children())
            for cat,sev,detail,amt in ex: self.tree.insert("","end",values=(cat,sev,detail,f"R {amt:,.2f}" if amt else "—"))
            self.status.config(text=f"Review period: {a} to {b} | Read-only")
        except Exception as e: messagebox.showerror("Audit & Compliance",str(e),parent=self)
    def export_csv(self):
        try: a,b=self._dates()
        except Exception as e: messagebox.showerror("Audit & Compliance",str(e),parent=self); return
        p=filedialog.asksaveasfilename(parent=self,defaultextension=".csv",filetypes=(("CSV files","*.csv"),),initialfile=f"compliance_{b}.csv")
        if not p:return
        c=sqlite3.connect(DB_PATH,timeout=10); ex=compliance_exceptions(c,a,b); c.close()
        with open(p,"w",newline="",encoding="utf-8-sig") as f:
            w=csv.writer(f); w.writerow(["BKPOS Audit & Compliance Review",a,b]); w.writerow(["Category","Severity","Exception / Finding","Amount"]); w.writerows(ex)
        messagebox.showinfo("Audit & Compliance","CSV exported successfully.",parent=self)
