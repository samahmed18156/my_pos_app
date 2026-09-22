"""BKPOS Phase 13: Advanced inventory forecasting and demand planning.
Read-only analytics; never posts stock or purchase transactions.
"""
from __future__ import annotations
import csv, sqlite3, tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
from core.config import DB_PATH

def _conn():
    c=sqlite3.connect(DB_PATH, timeout=10); c.execute('PRAGMA foreign_keys=ON'); return c

def _dates(start,end):
    datetime.strptime(start,'%Y-%m-%d'); datetime.strptime(end,'%Y-%m-%d')
    if start>end: raise ValueError('From date cannot be after To date')

def demand_forecast(conn,start,end,forecast_days=30):
    _dates(start,end); forecast_days=max(1,int(forecast_days))
    end_d=datetime.strptime(end,'%Y-%m-%d').date(); start_d=datetime.strptime(start,'%Y-%m-%d').date()
    days=max(1,(end_d-start_d).days+1); recent_start=max(start_d,end_d-timedelta(days=min(13,days-1)))
    rows=conn.execute("""SELECT p.barcode,p.description,COALESCE(p.category,''),COALESCE(p.soh,0),COALESCE(p.cost_price,0),COALESCE(p.min_stock,0),
        COALESCE((SELECT SUM(si.qty) FROM sale_items si JOIN sales_history s ON s.id=si.sale_id WHERE si.barcode=p.barcode AND date(s.timestamp) BETWEEN ? AND ? AND COALESCE(s.voided,0)=0 AND COALESCE(s.status,'COMPLETED')='COMPLETED'),0),
        COALESCE((SELECT SUM(si.qty) FROM sale_items si JOIN sales_history s ON s.id=si.sale_id WHERE si.barcode=p.barcode AND date(s.timestamp) BETWEEN ? AND ? AND COALESCE(s.voided,0)=0 AND COALESCE(s.status,'COMPLETED')='COMPLETED'),0)
        FROM products p WHERE COALESCE(p.active,1)=1 ORDER BY p.description""",
        (start,end,recent_start.isoformat(),end)).fetchall()
    out=[]
    for b,d,cat,soh,cost,mn,total,recent in rows:
        daily=float(total or 0)/days; recent_daily=float(recent or 0)/max(1,(end_d-recent_start).days+1)
        weighted=daily*0.4+recent_daily*0.6
        f30=weighted*forecast_days; days_cover=(float(soh)/weighted if weighted>0 else None)
        risk='STOCKOUT' if weighted>0 and days_cover is not None and days_cover<7 else ('WATCH' if weighted>0 and days_cover<14 else 'OK')
        out.append((b,d,cat,float(soh),float(cost),daily,recent_daily,weighted,f30,days_cover,risk,float(mn)))
    return out

def seasonality(conn,start,end):
    _dates(start,end)
    rows=conn.execute("""SELECT si.barcode,p.description,p.category,CAST(strftime('%w',s.timestamp) AS INTEGER) dow,COALESCE(SUM(si.qty),0)
      FROM sale_items si JOIN sales_history s ON s.id=si.sale_id JOIN products p ON p.barcode=si.barcode
      WHERE date(s.timestamp) BETWEEN ? AND ? AND COALESCE(s.voided,0)=0 AND COALESCE(s.status,'COMPLETED')='COMPLETED'
      GROUP BY si.barcode,p.description,p.category,dow ORDER BY si.barcode,dow""",(start,end)).fetchall()
    result=[]
    from collections import defaultdict
    x=defaultdict(list)
    for b,d,cat,dow,qty in rows:x[(b,d,cat)].append((dow,float(qty)))
    for (b,d,cat),vals in x.items():
        avg=sum(q for _,q in vals)/len(vals); peak=max(vals,key=lambda z:z[1]); result.append((b,d,cat,avg,peak[0],peak[1],(peak[1]/avg if avg else 0)))
    return sorted(result,key=lambda r:r[6],reverse=True)

def inventory_forecast(conn,start,end,forecast_days=30):
    return demand_forecast(conn,start,end,forecast_days)

class InventoryForecastingWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); self.title('BKPOS Advanced Inventory Forecasting & Demand Planning'); self.geometry('1450x840'); self.minsize(1200,700); self.configure(bg='#eef2f7'); self.transient(parent); self._build(); self._set_period(30); self.refresh(); self.bind('<Escape>',lambda e:self.destroy())
    def _build(self):
        tk.Label(self,text='ADVANCED INVENTORY FORECASTING & DEMAND PLANNING',font=('Segoe UI',20,'bold'),bg='#2c5282',fg='white',pady=14).pack(fill='x')
        bar=tk.Frame(self,bg='#eef2f7',pady=10); bar.pack(fill='x',padx=15)
        for label,attr in (('From','frm'),('To','to')):
            tk.Label(bar,text=label,bg='#eef2f7',font=('Segoe UI',10,'bold')).pack(side='left'); e=tk.Entry(bar,width=12); setattr(self,attr,e); e.pack(side='left',padx=5)
        for d,label in ((1,'Today'),(7,'7 Days'),(30,'30 Days'),(90,'90 Days')): tk.Button(bar,text=label,command=lambda x=d:self._set_period(x)).pack(side='left',padx=3)
        tk.Label(bar,text='Forecast days',bg='#eef2f7').pack(side='left',padx=(15,3)); self.fd=tk.Entry(bar,width=6); self.fd.insert(0,'30'); self.fd.pack(side='left')
        tk.Button(bar,text='RUN FORECAST',font=('Segoe UI',10,'bold'),command=self.refresh).pack(side='left',padx=8); tk.Button(bar,text='EXPORT CSV',command=self.export_csv).pack(side='left',padx=3); self.status=tk.Label(bar,text='',bg='#eef2f7'); self.status.pack(side='left',padx=10)
        nb=ttk.Notebook(self); nb.pack(fill='both',expand=True,padx=15,pady=10)
        self.fc=tk.Frame(nb,bg='white'); self.se=tk.Frame(nb,bg='white'); self.risk=tk.Frame(nb,bg='white')
        nb.add(self.fc,text='Demand Forecast'); nb.add(self.se,text='Weekly Seasonality'); nb.add(self.risk,text='Inventory Risk')
        cols=('barcode','product','category','soh','daily','recent','weighted','forecast','cover','risk','minimum')
        heads=('Barcode','Product','Category','On Hand','Avg/Day','Recent/Day','Forecast/Day','Forecast Units','Days Cover','Risk','Minimum')
        self.tree=self._tree(self.fc,cols,heads)
        self.setree=self._tree(self.se,('barcode','product','category','avg','peakday','peak','index'),('Barcode','Product','Category','Avg Daily Units','Peak Weekday','Peak Units','Seasonality Index'))
        self.rtree=self._tree(self.risk,cols,heads)
    def _tree(self,parent,cols,heads):
        fr=tk.Frame(parent,bg='white'); fr.pack(fill='both',expand=True,padx=12,pady=12); t=ttk.Treeview(fr,columns=cols,show='headings')
        for c,h in zip(cols,heads): t.heading(c,text=h); t.column(c,width=115,anchor='w' if c in ('barcode','product','category','risk','peakday') else 'e')
        sy=ttk.Scrollbar(fr,orient='vertical',command=t.yview); t.configure(yscrollcommand=sy.set); t.pack(side='left',fill='both',expand=True); sy.pack(side='right',fill='y'); return t
    def _set_period(self,days):
        end=datetime.now().date(); start=end-timedelta(days=days-1); self.frm.delete(0,'end'); self.frm.insert(0,start.isoformat()); self.to.delete(0,'end'); self.to.insert(0,end.isoformat())
    def refresh(self):
        try:
            start,end=self.frm.get().strip(),self.to.get().strip(); fd=int(self.fd.get().strip() or 30)
            if fd<1: raise ValueError('Forecast days must be positive')
            c=_conn()
            try: forecast=demand_forecast(c,start,end,fd); seas=seasonality(c,start,end)
            finally:c.close()
            self.tree.delete(*self.tree.get_children()); self.rtree.delete(*self.rtree.get_children()); self.setree.delete(*self.setree.get_children())
            riskrows=[]
            for r in forecast:
                vals=(r[0],r[1],r[2],f'{r[3]:g}',f'{r[5]:.2f}',f'{r[6]:.2f}',f'{r[7]:.2f}',f'{r[8]:.1f}',('∞' if r[9] is None else f'{r[9]:.1f}'),r[10],f'{r[11]:g}')
                self.tree.insert('','end',values=vals)
                if r[10]!='OK': riskrows.append(vals)
            for r in sorted(riskrows,key=lambda x: (0 if x[9]=='STOCKOUT' else 1,x[8] if x[8]!='∞' else 99999)): self.rtree.insert('','end',values=r)
            names=['Sun','Mon','Tue','Wed','Thu','Fri','Sat']
            for r in seas:self.setree.insert('','end',values=(r[0],r[1],r[2],f'{r[3]:.2f}',names[int(r[4])],f'{r[5]:.2f}',f'{r[6]:.2f}x'))
            stockouts=sum(1 for r in forecast if r[10]=='STOCKOUT'); watch=sum(1 for r in forecast if r[10]=='WATCH')
            self.status.config(text=f'{start} to {end} | {len(forecast)} products | {stockouts} stockout risks | {watch} watch')
        except Exception as exc: messagebox.showerror('Inventory Forecasting',f'Could not load forecast:\n{exc}',parent=self)
    def export_csv(self):
        path=filedialog.asksaveasfilename(parent=self,title='Export Inventory Forecast',defaultextension='.csv',filetypes=(('CSV files','*.csv'),))
        if not path:return
        try:
            with open(path,'w',newline='',encoding='utf-8-sig') as f:
                w=csv.writer(f); w.writerow(['BKPOS Advanced Inventory Forecast',f'{self.frm.get()} to {self.to.get()}']); w.writerow([])
                for title,t in (('Demand Forecast',self.tree),('Inventory Risk',self.rtree),('Weekly Seasonality',self.setree)):
                    w.writerow([title]); w.writerow([t.heading(c,'text') for c in t['columns']]); [w.writerow(t.item(i,'values')) for i in t.get_children()]; w.writerow([])
            messagebox.showinfo('Export Complete',f'Forecast exported to:\n{path}',parent=self)
        except Exception as exc: messagebox.showerror('Export Failed',str(exc),parent=self)
