"""BKPOS Executive Decision Support.

Read-only management intelligence: period comparison, branch performance,
product concentration, sales pace and actionable operational alerts. No
posting, stock, accounting, pricing or customer records are modified.
"""
from __future__ import annotations

import csv
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta

from core.config import DB_PATH
from core.logger import logger as _bkpos_logger


def _conn():
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.execute("PRAGMA foreign_keys=ON")
    return c


def _period(value):
    datetime.strptime(value, "%Y-%m-%d")
    return value


def _money(v):
    return f"R {float(v or 0):,.2f}"


def _sales_where(alias="s"):
    return (f"date({alias}.timestamp) BETWEEN ? AND ? "
            f"AND COALESCE({alias}.voided,0)=0 "
            f"AND COALESCE({alias}.status,'COMPLETED')='COMPLETED'")


def previous_period(start, end):
    a = datetime.strptime(start, "%Y-%m-%d").date()
    b = datetime.strptime(end, "%Y-%m-%d").date()
    days = (b - a).days + 1
    pb = a - timedelta(days=1)
    pa = pb - timedelta(days=days - 1)
    return pa.isoformat(), pb.isoformat()


def executive_summary(conn, start, end):
    ps, pe = previous_period(start, end)
    q = f"SELECT COALESCE(SUM(total_amount),0),COALESCE(SUM(total_cost),0),COUNT(*) FROM sales_history s WHERE {_sales_where()}"
    cur = conn.execute(q, (start, end)).fetchone()
    prev = conn.execute(q, (ps, pe)).fetchone()
    sales, cost, tx = float(cur[0]), float(cur[1]), int(cur[2])
    psales, pcost, ptx = float(prev[0]), float(prev[1]), int(prev[2])
    profit, pprofit = sales-cost, psales-pcost
    days = (datetime.strptime(end, "%Y-%m-%d").date()-datetime.strptime(start, "%Y-%m-%d").date()).days+1
    growth = ((sales-psales)/psales*100) if psales else None
    return {
        "sales": sales, "cost": cost, "profit": profit, "transactions": tx,
        "avg_basket": sales/tx if tx else 0, "sales_per_day": sales/days,
        "profit_margin": profit/sales*100 if sales else 0,
        "previous_sales": psales, "previous_profit": pprofit, "previous_transactions": ptx,
        "growth_pct": growth, "days": days,
    }


def branch_performance(conn, start, end):
    rows = conn.execute(f"""SELECT COALESCE(s.branch_id,0),COALESCE(s.branch_name,'Unassigned'),
        COUNT(*),COALESCE(SUM(s.total_amount),0),COALESCE(SUM(s.total_cost),0)
        FROM sales_history s WHERE {_sales_where()} GROUP BY s.branch_id,s.branch_name
        ORDER BY SUM(s.total_amount) DESC""", (start,end)).fetchall()
    return [(r[0],r[1],int(r[2]),float(r[3]),float(r[4]),float(r[3])-float(r[4])) for r in rows]


def product_performance(conn, start, end, limit=15):
    rows = conn.execute(f"""SELECT COALESCE(si.barcode,''),COALESCE(si.description,''),
        COALESCE(SUM(si.qty),0),COALESCE(SUM(si.value),0),COALESCE(SUM(si.qty*COALESCE(si.cost_price,0)),0)
        FROM sale_items si JOIN sales_history s ON s.id=si.sale_id
        WHERE {_sales_where()} GROUP BY si.barcode,si.description
        ORDER BY SUM(si.value) DESC LIMIT ?""", (start,end,int(limit))).fetchall()
    return [(r[0],r[1],float(r[2]),float(r[3]),float(r[4]),float(r[3])-float(r[4])) for r in rows]


def decision_alerts(conn, start, end):
    alerts=[]
    summary=executive_summary(conn,start,end)
    if summary["growth_pct"] is not None and summary["growth_pct"] < -10:
        alerts.append(("HIGH","Sales decline",f"Sales are {summary['growth_pct']:.1f}% versus the previous period."))
    if summary["profit_margin"] < 10 and summary["sales"] > 0:
        alerts.append(("HIGH","Low margin",f"Period gross margin is only {summary['profit_margin']:.1f}%."))
    try:
        out=conn.execute("SELECT COUNT(*) FROM products WHERE COALESCE(active,1)=1 AND COALESCE(soh,0)<=COALESCE(min_stock,0)").fetchone()[0]
        if out: alerts.append(("MEDIUM","Reorder pressure",f"{int(out)} active products are at or below minimum stock."))
    except sqlite3.Error as exc:
        _bkpos_logger.warning("Executive decision alert query skipped: %s", exc, exc_info=True)
    try:
        dead=conn.execute("""SELECT COUNT(*) FROM products p WHERE COALESCE(p.active,1)=1 AND COALESCE(p.soh,0)>0
          AND NOT EXISTS (SELECT 1 FROM sale_items si JOIN sales_history s ON s.id=si.sale_id
          WHERE si.barcode=p.barcode AND {_sw})""".format(_sw=_sales_where("s")),(start,end)).fetchone()[0]
        if dead: alerts.append(("LOW","Unsold inventory",f"{int(dead)} stocked products had no completed sale in the selected period."))
    except sqlite3.Error as exc:
        _bkpos_logger.warning("Executive decision alert query skipped: %s", exc, exc_info=True)
    return alerts


class ExecutiveDecisionSupportWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); self.parent=parent
        self.title("BKPOS Executive Decision Support"); self.geometry("1320x860"); self.minsize(1150,720)
        self.configure(bg="#eef2f7"); self.transient(parent); self.grab_set(); self._build(); self._set_period(30); self.refresh()

    def _build(self):
        tk.Label(self,text="EXECUTIVE DECISION SUPPORT",font=("Segoe UI",20,"bold"),bg="#2c5282",fg="white",pady=14).pack(fill="x")
        bar=tk.Frame(self,bg="#eef2f7",pady=10); bar.pack(fill="x",padx=15)
        for label,attr in (("From","frm"),("To","to")):
            tk.Label(bar,text=label,bg="#eef2f7",font=("Segoe UI",10,"bold")).pack(side="left")
            e=tk.Entry(bar,width=12); setattr(self,attr,e); e.pack(side="left",padx=5)
        for d,label in ((1,"Today"),(7,"7 Days"),(30,"30 Days"),(90,"90 Days")):
            tk.Button(bar,text=label,command=lambda x=d:self._set_period(x)).pack(side="left",padx=3)
        tk.Button(bar,text="RUN DECISION VIEW",font=("Segoe UI",10,"bold"),command=self.refresh).pack(side="left",padx=8)
        tk.Button(bar,text="EXPORT CSV",command=self.export_csv).pack(side="left",padx=3)
        self.status=tk.Label(bar,text="",bg="#eef2f7",anchor="w"); self.status.pack(side="left",padx=10)
        cards=tk.Frame(self,bg="#eef2f7"); cards.pack(fill="x",padx=15,pady=5); self.cards={}
        for i,k in enumerate(("Sales","Profit","Margin","Growth","Transactions","Avg Basket")):
            f=tk.Frame(cards,bg="white",bd=1,relief="solid"); f.grid(row=0,column=i,padx=4,sticky="nsew"); cards.grid_columnconfigure(i,weight=1)
            tk.Label(f,text=k,bg="white",font=("Segoe UI",9,"bold")).pack(pady=(9,2)); v=tk.Label(f,text="—",bg="white",font=("Segoe UI",15,"bold")); v.pack(pady=(0,10)); self.cards[k]=v
        nb=ttk.Notebook(self); nb.pack(fill="both",expand=True,padx=15,pady=10)
        self.branch_tab=tk.Frame(nb,bg="white"); self.product_tab=tk.Frame(nb,bg="white"); self.alert_tab=tk.Frame(nb,bg="white")
        nb.add(self.branch_tab,text="Branch Performance"); nb.add(self.product_tab,text="Product Performance"); nb.add(self.alert_tab,text="Decision Alerts")
        self.branch=self._tree(self.branch_tab,("id","branch","tx","sales","profit","margin"),("ID","Branch","Transactions","Sales","Profit","Margin"),(70,280,120,160,160,110))
        self.product=self._tree(self.product_tab,("barcode","product","units","sales","profit","share"),("Barcode","Product","Units","Sales","Profit","Sales Share"),(160,330,100,160,160,110))
        self.alert=self._tree(self.alert_tab,("level","issue","detail"),("Priority","Decision Area","Detail"),(110,220,720))

    def _tree(self,parent,cols,heads,widths):
        fr=tk.Frame(parent,bg="white"); fr.pack(fill="both",expand=True,padx=12,pady=12)
        t=ttk.Treeview(fr,columns=cols,show="headings")
        for c,h,w in zip(cols,heads,widths): t.heading(c,text=h); t.column(c,width=w,anchor="e" if c in ("id","tx","units","sales","profit","margin","share") else "w")
        sy=ttk.Scrollbar(fr,orient="vertical",command=t.yview); t.configure(yscrollcommand=sy.set); t.pack(side="left",fill="both",expand=True); sy.pack(side="right",fill="y"); return t

    def _set_period(self,days):
        end=datetime.now().date(); start=end-timedelta(days=days-1)
        self.frm.delete(0,"end"); self.frm.insert(0,start.isoformat()); self.to.delete(0,"end"); self.to.insert(0,end.isoformat())

    def refresh(self):
        try:
            start,end=_period(self.frm.get().strip()),_period(self.to.get().strip())
            if start>end: raise ValueError("From date cannot be after To date")
            c=_conn()
            try: s=executive_summary(c,start,end); branches=branch_performance(c,start,end); products=product_performance(c,start,end); alerts=decision_alerts(c,start,end)
            finally: c.close()
            self.cards["Sales"].config(text=_money(s["sales"])); self.cards["Profit"].config(text=_money(s["profit"])); self.cards["Margin"].config(text=f"{s['profit_margin']:.1f}%"); self.cards["Growth"].config(text=(f"{s['growth_pct']:+.1f}%" if s['growth_pct'] is not None else "N/A")); self.cards["Transactions"].config(text=f"{s['transactions']:,}"); self.cards["Avg Basket"].config(text=_money(s["avg_basket"]))
            for t in (self.branch,self.product,self.alert): t.delete(*t.get_children())
            for bid,name,tx,sales,cost,profit in branches: self.branch.insert("","end",values=(bid,name,f"{tx:,}",_money(sales),_money(profit),f"{profit/sales*100:.1f}%" if sales else "0.0%"))
            total=s["sales"] or 1
            for code,name,units,sales,cost,profit in products: self.product.insert("","end",values=(code,name,f"{units:g}",_money(sales),_money(profit),f"{sales/total*100:.1f}%"))
            for level,issue,detail in alerts: self.alert.insert("","end",values=(level,issue,detail))
            self.status.config(text=f"Decision view: {start} to {end} | Previous period: {s['previous_sales'] and _money(s['previous_sales']) or 'R 0.00'} sales")
            self.last=(s,branches,products,alerts)
        except Exception as exc: messagebox.showerror("Executive Decision Support",f"Could not load decision data:\n{exc}",parent=self)

    def export_csv(self):
        if not hasattr(self,"last"): return
        path=filedialog.asksaveasfilename(parent=self,title="Export Executive Decision Support",defaultextension=".csv",filetypes=(("CSV files","*.csv"),),initialfile="executive_decision_support.csv")
        if not path:return
        s,branches,products,alerts=self.last
        try:
            with open(path,"w",newline="",encoding="utf-8-sig") as f:
                w=csv.writer(f); w.writerow(["BKPOS Executive Decision Support",f"{self.frm.get()} to {self.to.get()}"]); w.writerow([])
                w.writerow(["KPI","Value"]); w.writerows([[k,v] for k,v in s.items()]); w.writerow([])
                w.writerow(["Branch","Transactions","Sales","Profit"]); w.writerows([[r[1],r[2],r[3],r[5]] for r in branches]); w.writerow([])
                w.writerow(["Barcode","Product","Units","Sales","Profit","Sales Share"]); total=s["sales"] or 1; w.writerows([[r[0],r[1],r[2],r[3],r[5],r[3]/total*100] for r in products]); w.writerow([])
                w.writerow(["Priority","Decision Area","Detail"]); w.writerows(alerts)
            messagebox.showinfo("Export Complete",f"Executive decision support exported to:\n{path}",parent=self)
        except Exception as exc: messagebox.showerror("Export Failed",str(exc),parent=self)
