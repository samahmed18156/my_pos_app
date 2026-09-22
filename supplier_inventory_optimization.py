"""BKPOS Phase 7: Purchasing, supplier and inventory optimization.

Management tooling is read-only against transaction data. Suggested orders and
analysis never post stock, GRNs, supplier balances or accounting entries.
"""
from __future__ import annotations
import csv, sqlite3, tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
from core.config import DB_PATH


def _conn():
    c=sqlite3.connect(DB_PATH, timeout=10); c.execute("PRAGMA foreign_keys=ON"); return c

def _dates(start,end):
    datetime.strptime(start,'%Y-%m-%d'); datetime.strptime(end,'%Y-%m-%d')
    if start>end: raise ValueError('From date cannot be after To date')

def supplier_performance(conn,start,end):
    _dates(start,end)
    return conn.execute("""SELECT COALESCE(g.supplier_name,''),COUNT(DISTINCT g.id),
        COALESCE(SUM(g.total),0),COALESCE(SUM(g.outstanding),0),
        COALESCE(AVG(g.total),0),COALESCE(SUM(gi.qty_received),0)
        FROM grn_headers g LEFT JOIN grn_items gi ON gi.grn_id=g.id
        WHERE date(g.created_at) BETWEEN ? AND ? GROUP BY g.supplier_id,g.supplier_name
        ORDER BY SUM(g.total) DESC""",(start,end)).fetchall()

def cost_variance(conn,start,end):
    _dates(start,end)
    return conn.execute("""SELECT gi.barcode,COALESCE(gi.description,p.description),
        COALESCE(p.cost_price,0),COALESCE(AVG(gi.cost_price),0),COALESCE(SUM(gi.qty_received),0),
        COALESCE(SUM(gi.value),0)
        FROM grn_items gi JOIN grn_headers g ON g.id=gi.grn_id
        LEFT JOIN products p ON p.barcode=gi.barcode
        WHERE date(g.created_at) BETWEEN ? AND ? GROUP BY gi.barcode,2,3
        HAVING ABS(AVG(gi.cost_price)-COALESCE(p.cost_price,0)) > 0.005
        ORDER BY ABS(AVG(gi.cost_price)-COALESCE(p.cost_price,0)) DESC""",(start,end)).fetchall()

def dead_stock(conn,start,end,days=60):
    _dates(start,end)
    cutoff=(datetime.strptime(end,'%Y-%m-%d').date()-timedelta(days=int(days))).isoformat()
    sold={r[0]:float(r[1] or 0) for r in conn.execute("""SELECT si.barcode,SUM(si.qty) FROM sale_items si JOIN sales_history s ON s.id=si.sale_id
        WHERE date(s.timestamp) BETWEEN ? AND ? AND COALESCE(s.voided,0)=0 AND COALESCE(s.status,'COMPLETED')='COMPLETED' GROUP BY si.barcode""",(cutoff,end))}
    rows=conn.execute("""SELECT barcode,description,COALESCE(soh,0),COALESCE(cost_price,0),COALESCE(category,'')
        FROM products WHERE COALESCE(active,1)=1 AND COALESCE(soh,0)>0 ORDER BY soh*cost_price DESC""").fetchall()
    return [(b,d,float(q),float(c),cat,float(sold.get(b,0)),float(q)*float(c)) for b,d,q,c,cat in rows if sold.get(b,0)<=0]

def reorder_suggestions(conn,start,end,lead_days=7,safety_days=3):
    _dates(start,end); days=max(1,(datetime.strptime(end,'%Y-%m-%d').date()-datetime.strptime(start,'%Y-%m-%d').date()).days+1)
    demand=dict(conn.execute("""SELECT si.barcode,COALESCE(SUM(si.qty),0)/? FROM sale_items si JOIN sales_history s ON s.id=si.sale_id
        WHERE date(s.timestamp) BETWEEN ? AND ? AND COALESCE(s.voided,0)=0 AND COALESCE(s.status,'COMPLETED')='COMPLETED' GROUP BY si.barcode""",(days,start,end)).fetchall())
    rows=conn.execute("""SELECT barcode,description,COALESCE(soh,0),COALESCE(min_stock,0),COALESCE(reorder_qty,0),COALESCE(cost_price,0),COALESCE(category,'')
        FROM products WHERE COALESCE(active,1)=1 ORDER BY description""").fetchall()
    out=[]
    for b,d,soh,mn,rq,cost,cat in rows:
        daily=float(demand.get(b,0) or 0); target=max(float(mn),daily*(lead_days+safety_days)); qty=max(float(rq),target-float(soh))
        if qty>0: out.append((b,d,cat,float(soh),float(mn),daily,qty,float(cost),qty*float(cost)))
    return sorted(out,key=lambda x:x[8],reverse=True)

class SupplierInventoryOptimizationWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); self.title('BKPOS Purchasing & Inventory Optimization'); self.geometry('1350x820'); self.minsize(1150,700); self.configure(bg='#eef2f7'); self.transient(parent)
        self._build(); self._set_period(30); self.refresh(); self.bind('<Escape>',lambda e:self.destroy())
    def _build(self):
        tk.Label(self,text='PURCHASING & INVENTORY OPTIMIZATION',font=('Segoe UI',20,'bold'),bg='#2c5282',fg='white',pady=14).pack(fill='x')
        bar=tk.Frame(self,bg='#eef2f7',pady=10); bar.pack(fill='x',padx=15)
        for label,attr in (('From','frm'),('To','to')):
            tk.Label(bar,text=label,bg='#eef2f7',font=('Segoe UI',10,'bold')).pack(side='left'); e=tk.Entry(bar,width=12); setattr(self,attr,e); e.pack(side='left',padx=5)
        for d,label in ((1,'Today'),(7,'7 Days'),(30,'30 Days'),(90,'90 Days')): tk.Button(bar,text=label,command=lambda x=d:self._set_period(x)).pack(side='left',padx=3)
        tk.Label(bar,text='Dead stock days',bg='#eef2f7').pack(side='left',padx=(15,3)); self.dead=tk.Entry(bar,width=7); self.dead.insert(0,'60'); self.dead.pack(side='left')
        tk.Button(bar,text='RUN ANALYSIS',font=('Segoe UI',10,'bold'),command=self.refresh).pack(side='left',padx=8); tk.Button(bar,text='EXPORT CSV',command=self.export_csv).pack(side='left',padx=3); self.status=tk.Label(bar,text='',bg='#eef2f7'); self.status.pack(side='left',padx=10)
        nb=ttk.Notebook(self); nb.pack(fill='both',expand=True,padx=15,pady=10)
        self.sup_tab=tk.Frame(nb,bg='white'); self.cost_tab=tk.Frame(nb,bg='white'); self.reorder_tab=tk.Frame(nb,bg='white'); self.dead_tab=tk.Frame(nb,bg='white')
        nb.add(self.sup_tab,text='Supplier Performance'); nb.add(self.cost_tab,text='Cost Variance'); nb.add(self.reorder_tab,text='Suggested Orders'); nb.add(self.dead_tab,text='Dead Stock')
        self.sup=self._tree(self.sup_tab,('supplier','grns','purchases','outstanding','avg','units'),('Supplier','GRNs','Purchases','Outstanding','Avg GRN','Units'),(300,90,160,160,140,110))
        self.cost=self._tree(self.cost_tab,('barcode','product','current','avg','units','value'),('Barcode','Product','Current Cost','Avg Received Cost','Units','Purchase Value'),(150,300,140,170,100,160))
        self.reorder=self._tree(self.reorder_tab,('barcode','product','category','soh','min','daily','qty','cost','value'),('Barcode','Product','Category','On Hand','Minimum','Daily Use','Order Qty','Unit Cost','Order Value'),(140,260,140,90,90,100,100,110,140))
        self.deadtree=self._tree(self.dead_tab,('barcode','product','category','soh','cost','sold','value'),('Barcode','Product','Category','On Hand','Unit Cost','Sold in Window','Stock Value'),(150,280,140,100,110,130,150))
    def _tree(self,parent,cols,heads,widths):
        fr=tk.Frame(parent,bg='white'); fr.pack(fill='both',expand=True,padx=12,pady=12); t=ttk.Treeview(fr,columns=cols,show='headings')
        for c,h,w in zip(cols,heads,widths): t.heading(c,text=h); t.column(c,width=w,anchor='w' if c in ('supplier','product','category','barcode') else 'e')
        sy=ttk.Scrollbar(fr,orient='vertical',command=t.yview); t.configure(yscrollcommand=sy.set); t.pack(side='left',fill='both',expand=True); sy.pack(side='right',fill='y'); return t
    def _set_period(self,days):
        end=datetime.now().date(); start=end-timedelta(days=days-1); self.frm.delete(0,'end'); self.frm.insert(0,start.isoformat()); self.to.delete(0,'end'); self.to.insert(0,end.isoformat())
    def refresh(self):
        try:
            start,end=self.frm.get().strip(),self.to.get().strip(); days=int(self.dead.get().strip() or 60)
            if days<1: raise ValueError('Dead stock days must be positive')
            c=_conn()
            try: sup=supplier_performance(c,start,end); cv=cost_variance(c,start,end); ro=reorder_suggestions(c,start,end); ds=dead_stock(c,start,end,days)
            finally: c.close()
            for t in (self.sup,self.cost,self.reorder,self.deadtree): t.delete(*t.get_children())
            for r in sup: self.sup.insert('','end',values=(r[0],r[1],f'R {r[2]:,.2f}',f'R {r[3]:,.2f}',f'R {r[4]:,.2f}',f'{r[5]:,.2f}'))
            for r in cv: self.cost.insert('','end',values=(r[0],r[1],f'R {r[2]:,.2f}',f'R {r[3]:,.2f}',f'{r[4]:,.2f}',f'R {r[5]:,.2f}'))
            for r in ro: self.reorder.insert('','end',values=(r[0],r[1],r[2],f'{r[3]:g}',f'{r[4]:g}',f'{r[5]:.2f}',f'{r[6]:g}',f'R {r[7]:,.2f}',f'R {r[8]:,.2f}'))
            for r in ds: self.deadtree.insert('','end',values=(r[0],r[1],r[4],f'{r[2]:g}',f'R {r[3]:,.2f}',f'{r[5]:g}',f'R {r[6]:,.2f}'))
            self.status.config(text=f'{start} to {end} | {len(ro)} reorder suggestions | {len(ds)} dead-stock items')
        except Exception as exc: messagebox.showerror('Purchasing & Inventory',f'Could not load analysis:\n{exc}',parent=self)
    def export_csv(self):
        path=filedialog.asksaveasfilename(parent=self,title='Export Purchasing Analysis',defaultextension='.csv',filetypes=(('CSV files','*.csv'),))
        if not path:return
        try:
            with open(path,'w',newline='',encoding='utf-8-sig') as f:
                w=csv.writer(f); w.writerow(['BKPOS Purchasing & Inventory Optimization',f'{self.frm.get()} to {self.to.get()}']); w.writerow([])
                for title,t in (('Supplier Performance',self.sup),('Cost Variance',self.cost),('Suggested Orders',self.reorder),('Dead Stock',self.deadtree)):
                    w.writerow([title]); w.writerow([t.heading(c,'text') for c in t['columns']]); [w.writerow(t.item(i,'values')) for i in t.get_children()]; w.writerow([])
            messagebox.showinfo('Export Complete',f'Analysis exported to:\n{path}',parent=self)
        except Exception as exc: messagebox.showerror('Export Failed',str(exc),parent=self)
