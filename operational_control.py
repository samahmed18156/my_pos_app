"""BKPOS Phase 3 operational control and stock intelligence.

Read-only management controls built on the existing transaction ledger.  No
sales, inventory, accounting, pricing or master-data posting is performed.
"""
from __future__ import annotations
import csv
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
from core.config import DB_PATH


def _conn():
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.execute("PRAGMA foreign_keys=ON")
    return c


def _period(start, end):
    datetime.strptime(start, "%Y-%m-%d")
    datetime.strptime(end, "%Y-%m-%d")
    if start > end:
        raise ValueError("From date cannot be after To date")


def _sales_where(start, end):
    return ("date(s.timestamp) BETWEEN ? AND ? AND COALESCE(s.voided,0)=0 "
            "AND COALESCE(s.status,'COMPLETED')='COMPLETED'"), [start, end]


def category_performance(conn, start, end):
    where, args = _sales_where(start, end)
    return conn.execute(f"""SELECT COALESCE(NULLIF(TRIM(p.category),''),'Uncategorised') category,
        COALESCE(SUM(si.qty),0) units, COALESCE(SUM(si.qty*si.price),0) sales,
        COALESCE(SUM(si.qty*(si.price-COALESCE(si.cost_price,p.cost_price,0))),0) profit
        FROM sale_items si JOIN sales_history s ON s.id=si.sale_id
        LEFT JOIN products p ON p.barcode=si.barcode WHERE {where}
        GROUP BY 1 ORDER BY sales DESC""", args).fetchall()


def stock_intelligence(conn, start, end, *, lead_days=7, safety_days=3):
    where, args = _sales_where(start, end)
    days = max(1, (datetime.strptime(end, "%Y-%m-%d").date() - datetime.strptime(start, "%Y-%m-%d").date()).days + 1)
    demand = conn.execute(f"""SELECT si.barcode, COALESCE(SUM(si.qty),0)/? daily_units
        FROM sale_items si JOIN sales_history s ON s.id=si.sale_id WHERE {where}
        GROUP BY si.barcode""", [days, *args]).fetchall()
    daily = dict(demand)
    rows = conn.execute("""SELECT barcode,description,COALESCE(soh,0),COALESCE(cost_price,0),
        COALESCE(selling_price,0),COALESCE(min_stock,0),COALESCE(category,'') FROM products
        WHERE COALESCE(active,1)=1 ORDER BY description""").fetchall()
    result=[]
    for code, desc, soh, cost, price, minimum, category in rows:
        rate=float(daily.get(code,0) or 0)
        reorder=max(float(minimum or 0), rate*(lead_days+safety_days))
        suggested=max(0.0, reorder-float(soh or 0))
        status = "OUT OF STOCK" if soh <= 0 else "LOW STOCK" if soh <= minimum else "OK"
        if suggested > 0: status += " / REORDER"
        result.append((desc, code, category or "Uncategorised", float(soh), float(minimum), rate, suggested, status, float(cost)))
    return sorted(result, key=lambda r: (0 if r[7].startswith("OUT") else 1 if r[7].startswith("LOW") else 2, -r[6], r[0].lower()))


def product_velocity(conn, start, end):
    where, args = _sales_where(start, end)
    days=max(1,(datetime.strptime(end,"%Y-%m-%d").date()-datetime.strptime(start,"%Y-%m-%d").date()).days+1)
    return conn.execute(f"""SELECT si.barcode,COALESCE(si.description,p.description),COALESCE(p.category,'Uncategorised'),
        SUM(si.qty) units, SUM(si.qty*si.price) sales,
        SUM(si.qty*(si.price-COALESCE(si.cost_price,p.cost_price,0))) profit,
        SUM(si.qty)/? daily_units
        FROM sale_items si JOIN sales_history s ON s.id=si.sale_id LEFT JOIN products p ON p.barcode=si.barcode
        WHERE {where} GROUP BY si.barcode,2,3 ORDER BY units DESC""", [days,*args]).fetchall()


def performance_summary(conn, start, end, target=0.0):
    where,args=_sales_where(start,end)
    sales,txns=conn.execute(f"SELECT COALESCE(SUM(s.total_amount),0),COUNT(*) FROM sales_history s WHERE {where}",args).fetchone()
    days=max(1,(datetime.strptime(end,"%Y-%m-%d").date()-datetime.strptime(start,"%Y-%m-%d").date()).days+1)
    target_total=float(target or 0)*days
    sales=float(sales or 0)
    return {"sales":sales,"transactions":int(txns or 0),"days":days,"target":target_total,
            "variance":sales-target_total,"achievement":(sales/target_total*100 if target_total else None)}


class OperationalControlWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); self.parent=parent
        self.title("BKPOS Operational Control Center"); self.geometry("1280x820"); self.minsize(1100,700)
        self.configure(bg="#eef2f7"); self.transient(parent); self.grab_set(); self._build(); self._set_period(30); self.refresh()

    def _build(self):
        tk.Label(self,text="OPERATIONAL CONTROL CENTER",font=("Segoe UI",20,"bold"),bg="#2c5282",fg="white",pady=14).pack(fill="x")
        bar=tk.Frame(self,bg="#eef2f7",pady=10); bar.pack(fill="x",padx=15)
        for label,attr in (("From","frm"),("To","to")):
            tk.Label(bar,text=label,bg="#eef2f7",font=("Segoe UI",10,"bold")).pack(side="left")
            e=tk.Entry(bar,width=12); setattr(self,attr,e); e.pack(side="left",padx=5)
        for d,label in ((1,"Today"),(7,"7 Days"),(30,"30 Days"),(90,"90 Days")):
            tk.Button(bar,text=label,command=lambda x=d:self._set_period(x)).pack(side="left",padx=3)
        tk.Label(bar,text="Daily target R",bg="#eef2f7").pack(side="left",padx=(15,3))
        self.target=tk.Entry(bar,width=12); self.target.insert(0,"0"); self.target.pack(side="left")
        tk.Button(bar,text="RUN CONTROL",font=("Segoe UI",10,"bold"),command=self.refresh).pack(side="left",padx=8)
        tk.Button(bar,text="EXPORT CSV",command=self.export_csv).pack(side="left",padx=3)
        self.status=tk.Label(bar,text="",bg="#eef2f7"); self.status.pack(side="left",padx=10)
        cards=tk.Frame(self,bg="#eef2f7"); cards.pack(fill="x",padx=15,pady=5); self.cards={}
        for i,k in enumerate(("Sales","Target","Variance","Achievement","Reorder Items","Stock Value")):
            f=tk.Frame(cards,bg="white",bd=1,relief="solid"); f.grid(row=0,column=i,padx=4,sticky="nsew"); cards.grid_columnconfigure(i,weight=1)
            tk.Label(f,text=k,bg="white",font=("Segoe UI",9,"bold")).pack(pady=(9,2)); v=tk.Label(f,text="—",bg="white",font=("Segoe UI",14,"bold")); v.pack(pady=(0,10)); self.cards[k]=v
        nb=ttk.Notebook(self); nb.pack(fill="both",expand=True,padx=15,pady=10)
        self.cat_tab=tk.Frame(nb,bg="white"); self.vel_tab=tk.Frame(nb,bg="white"); self.stock_tab=tk.Frame(nb,bg="white")
        nb.add(self.cat_tab,text="Categories"); nb.add(self.vel_tab,text="Fast / Slow Movers"); nb.add(self.stock_tab,text="Reorder Control")
        self.cat=self._tree(self.cat_tab,("category","units","sales","profit","margin"),("Category","Units","Sales","Profit","Margin"),(300,100,150,150,100))
        self.vel=self._tree(self.vel_tab,("product","category","units","daily","sales","profit"),("Product","Category","Units","Daily Units","Sales","Profit"),(300,160,90,110,140,140))
        self.stock=self._tree(self.stock_tab,("product","barcode","category","soh","min","daily","reorder","status"),("Product","Barcode","Category","On Hand","Minimum","Daily Usage","Suggested Reorder","Status"),(260,150,150,90,90,110,140,190))

    def _tree(self,parent,cols,heads,widths):
        fr=tk.Frame(parent,bg="white"); fr.pack(fill="both",expand=True,padx=12,pady=12)
        t=ttk.Treeview(fr,columns=cols,show="headings")
        for c,h,w in zip(cols,heads,widths): t.heading(c,text=h); t.column(c,width=w,anchor="e" if c not in (cols[0],cols[1] if len(cols)>1 else "") else "w")
        sy=ttk.Scrollbar(fr,orient="vertical",command=t.yview); t.configure(yscrollcommand=sy.set); t.pack(side="left",fill="both",expand=True); sy.pack(side="right",fill="y"); return t

    def _set_period(self,days):
        end=datetime.now().date(); start=end-timedelta(days=days-1)
        self.frm.delete(0,"end"); self.frm.insert(0,start.isoformat()); self.to.delete(0,"end"); self.to.insert(0,end.isoformat())

    def refresh(self):
        try:
            start,end=self.frm.get().strip(),self.to.get().strip(); _period(start,end)
            target=float(self.target.get().strip() or 0)
            if target<0: raise ValueError("Daily target cannot be negative")
            c=_conn()
            try:
                s=performance_summary(c,start,end,target); cats=category_performance(c,start,end); vel=product_velocity(c,start,end); stock=stock_intelligence(c,start,end)
                stock_value=c.execute("SELECT COALESCE(SUM(soh*cost_price),0) FROM products WHERE COALESCE(active,1)=1").fetchone()[0] or 0
            finally: c.close()
            self.cards["Sales"].config(text=f"R {s['sales']:,.2f}"); self.cards["Target"].config(text=f"R {s['target']:,.2f}"); self.cards["Variance"].config(text=f"R {s['variance']:,.2f}"); self.cards["Achievement"].config(text=(f"{s['achievement']:.1f}%" if s['achievement'] is not None else "—")); self.cards["Reorder Items"].config(text=f"{sum(1 for r in stock if r[6]>0):,}"); self.cards["Stock Value"].config(text=f"R {float(stock_value):,.2f}")
            for t in (self.cat,self.vel,self.stock): t.delete(*t.get_children())
            for cat,u,sa,p in cats: self.cat.insert("","end",values=(cat,f"{u:,.2f}",f"R {sa:,.2f}",f"R {p:,.2f}",f"{(p/sa*100 if sa else 0):.1f}%"))
            for code,desc,cat,u,sa,p,d in vel: self.vel.insert("","end",values=(desc,cat,f"{u:,.2f}",f"{d:.2f}",f"R {sa:,.2f}",f"R {p:,.2f}"))
            for desc,code,cat,soh,mn,d,reorder,status,cost in stock: self.stock.insert("","end",values=(desc,code,cat,f"{soh:g}",f"{mn:g}",f"{d:.2f}",f"{reorder:g}",status))
            self.status.config(text=f"Control: {start} to {end} | {s['transactions']:,} transactions")
        except Exception as exc: messagebox.showerror("Operational Control",f"Could not load control data:\n{exc}",parent=self)

    def export_csv(self):
        path=filedialog.asksaveasfilename(parent=self,title="Export Operational Control",defaultextension=".csv",filetypes=(("CSV files","*.csv"),))
        if not path: return
        try:
            with open(path,"w",newline="",encoding="utf-8-sig") as f:
                w=csv.writer(f); w.writerow(["BKPOS Operational Control",f"{self.frm.get()} to {self.to.get()}"]); w.writerow([])
                for title,tree in (("Categories",self.cat),("Fast / Slow Movers",self.vel),("Reorder Control",self.stock)):
                    w.writerow([title]); w.writerow([tree.heading(c,"text") for c in tree["columns"]])
                    for item in tree.get_children(): w.writerow(tree.item(item,"values"))
                    w.writerow([])
            messagebox.showinfo("Export Complete",f"Operational control exported to:\n{path}",parent=self)
        except Exception as exc: messagebox.showerror("Export Failed",str(exc),parent=self)
