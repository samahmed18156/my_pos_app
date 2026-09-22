"""BKPOS Price Scenario Simulator.

Non-posting what-if analysis: estimates the effect of a hypothetical price and
volume change using existing completed sales and product cost data. It never
changes prices, stock, customers, or accounting records.
"""
from __future__ import annotations
import sqlite3, tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from core.config import DB_PATH


def _conn():
    return sqlite3.connect(DB_PATH, timeout=10)


def scenario_rows(conn, start, end, price_pct, volume_pct, barcode_filter=""):
    datetime.strptime(start, "%Y-%m-%d"); datetime.strptime(end, "%Y-%m-%d")
    if start > end: raise ValueError("From date cannot be after To date")
    rows = conn.execute("""
        SELECT si.barcode, COALESCE(si.description,p.description,''),
               COALESCE(p.cost_price,0), COALESCE(SUM(si.qty),0),
               COALESCE(AVG(si.price),0)
        FROM sale_items si
        JOIN sales_history s ON s.id=si.sale_id
        LEFT JOIN products p ON p.barcode=si.barcode
        WHERE date(s.timestamp) BETWEEN ? AND ?
          AND COALESCE(s.voided,0)=0
          AND COALESCE(s.status,'COMPLETED')='COMPLETED'
          AND (?='' OR si.barcode=?)
        GROUP BY si.barcode,2,3
        ORDER BY SUM(si.qty*si.price) DESC
    """, (start,end,barcode_filter,barcode_filter)).fetchall()
    pp=float(price_pct)/100.0; vp=float(volume_pct)/100.0
    out=[]
    for code,name,cost,units,price in rows:
        units=float(units or 0); price=float(price or 0); cost=float(cost or 0)
        base_rev=units*price; base_profit=units*(price-cost)
        s_price=max(0.0,price*(1+pp)); s_units=max(0.0,units*(1+vp))
        s_rev=s_units*s_price; s_profit=s_units*(s_price-cost)
        out.append((code,name,cost,units,price,base_rev,base_profit,s_units,s_price,s_rev,s_profit,s_rev-base_rev,s_profit-base_profit))
    return out


class PriceScenarioSimulatorWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); self.parent=parent
        self.title("BKPOS — Price Scenario Simulator"); self.geometry("1320x760"); self.minsize(1100,650); self.configure(bg="#eef2f7"); self.transient(parent)
        self._build(); self._set_period(30); self.refresh(); self.bind("<Escape>",lambda e:self.destroy())

    def _build(self):
        tk.Label(self,text="PRICE SCENARIO SIMULATOR",font=("Segoe UI",20,"bold"),bg="#2c5282",fg="white",pady=14).pack(fill="x")
        tk.Label(self,text="What-if analysis only — no actual prices or transactions are changed.",font=("Segoe UI",10),bg="#eef2f7",fg="#555").pack(anchor="w",padx=16,pady=(10,4))
        bar=tk.Frame(self,bg="#eef2f7",pady=8); bar.pack(fill="x",padx=16)
        for label,attr in (("From","frm"),("To","to")):
            tk.Label(bar,text=label,bg="#eef2f7",font=("Segoe UI",10,"bold")).pack(side="left"); e=tk.Entry(bar,width=12); setattr(self,attr,e); e.pack(side="left",padx=5)
        for d,label in ((7,"7 Days"),(30,"30 Days"),(90,"90 Days")):
            tk.Button(bar,text=label,command=lambda x=d:self._set_period(x)).pack(side="left",padx=3)
        tk.Label(bar,text="Price change %",bg="#eef2f7").pack(side="left",padx=(16,3)); self.pp=tk.Entry(bar,width=8); self.pp.insert(0,"5"); self.pp.pack(side="left")
        tk.Label(bar,text="Expected volume change %",bg="#eef2f7").pack(side="left",padx=(12,3)); self.vp=tk.Entry(bar,width=8); self.vp.insert(0,"-3"); self.vp.pack(side="left")
        tk.Label(bar,text="Barcode (optional)",bg="#eef2f7").pack(side="left",padx=(12,3)); self.code=tk.Entry(bar,width=16); self.code.pack(side="left")
        tk.Button(bar,text="SIMULATE",font=("Segoe UI",10,"bold"),command=self.refresh).pack(side="left",padx=8)
        self.summary=tk.Label(self,text="",font=("Segoe UI",11,"bold"),bg="#eef2f7",anchor="w"); self.summary.pack(fill="x",padx=16,pady=8)
        fr=tk.Frame(self,bg="white"); fr.pack(fill="both",expand=True,padx=16,pady=(0,16))
        cols=("barcode","product","cost","units","price","base_profit","scenario_units","scenario_price","scenario_profit","profit_delta","revenue_delta")
        self.tree=ttk.Treeview(fr,columns=cols,show="headings")
        heads=("Barcode","Product","Cost","Base Units","Base Price","Base Profit","Scenario Units","Scenario Price","Scenario Profit","Profit Δ","Revenue Δ")
        widths=(130,250,100,95,105,125,110,115,135,110,110)
        for c,h,w in zip(cols,heads,widths): self.tree.heading(c,text=h); self.tree.column(c,width=w,anchor="w" if c in ("barcode","product") else "e")
        sy=ttk.Scrollbar(fr,orient="vertical",command=self.tree.yview); self.tree.configure(yscrollcommand=sy.set); self.tree.pack(side="left",fill="both",expand=True); sy.pack(side="right",fill="y")

    def _set_period(self,days):
        end=datetime.now().date(); start=end-timedelta(days=days-1)
        self.frm.delete(0,"end"); self.frm.insert(0,start.isoformat()); self.to.delete(0,"end"); self.to.insert(0,end.isoformat())

    def refresh(self):
        try:
            pp=float(self.pp.get()); vp=float(self.vp.get())
            if pp <= -100: raise ValueError("Price change must be greater than -100%.")
            if vp <= -100: raise ValueError("Volume change must be greater than -100%.")
            c=_conn()
            try: rows=scenario_rows(c,self.frm.get().strip(),self.to.get().strip(),pp,vp,self.code.get().strip())
            finally: c.close()
            self.tree.delete(*self.tree.get_children())
            for r in rows:
                self.tree.insert("","end",values=(r[0],r[1],f"R {r[2]:,.2f}",f"{r[3]:,.2f}",f"R {r[4]:,.2f}",f"R {r[6]:,.2f}",f"{r[7]:,.2f}",f"R {r[8]:,.2f}",f"R {r[10]:,.2f}",f"R {r[12]:+,.2f}",f"R {r[11]:+,.2f}"))
            base_profit=sum(r[6] for r in rows); scen_profit=sum(r[10] for r in rows); base_rev=sum(r[5] for r in rows); scen_rev=sum(r[9] for r in rows)
            self.summary.config(text=f"{len(rows)} products  |  Base revenue R {base_rev:,.2f} → Scenario R {scen_rev:,.2f}  |  Base profit R {base_profit:,.2f} → Scenario R {scen_profit:,.2f}  |  Profit change R {scen_profit-base_profit:+,.2f}")
        except Exception as exc: messagebox.showerror("Price Scenario Simulator",f"Could not run simulation:\n{exc}",parent=self)
