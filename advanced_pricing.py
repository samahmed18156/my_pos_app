"""BKPOS Phase 15 - Advanced Pricing & Promotion Management.

Management controls for scheduled prices, branch pricing, promotion calendars,
margin protection and pricing audit history. Existing checkout behavior is
preserved; this module provides controlled definitions and analysis only.
"""
import csv
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime
from core.config import DB_PATH


def connect(): return sqlite3.connect(DB_PATH)

def ensure_schema(conn=None):
    own = conn is None; c = conn or connect()
    c.execute("""CREATE TABLE IF NOT EXISTS price_schedules (
        id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL,
        branch_id INTEGER, new_price REAL NOT NULL, effective_date TEXT NOT NULL,
        end_date TEXT, min_margin REAL NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1,
        reason TEXT DEFAULT '', created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS price_change_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL,
        branch_id INTEGER, old_price REAL, new_price REAL NOT NULL,
        changed_at DATETIME DEFAULT CURRENT_TIMESTAMP, reason TEXT DEFAULT '')""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_price_schedule_dates ON price_schedules(active,effective_date,end_date)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_price_audit_product ON price_change_audit(product_id,changed_at)")
    if own: c.commit(); c.close()

def _cols(conn, table):
    try: return {r[1] for r in conn.execute(f'PRAGMA table_info({table})')}
    except Exception: return set()

def pricing_catalog(conn=None):
    own=conn is None; c=conn or connect(); ensure_schema(c)
    pc=_cols(c,'products')
    name='description' if 'description' in pc else ('name' if 'name' in pc else "'Product'")
    price='selling_price' if 'selling_price' in pc else ('price' if 'price' in pc else '0')
    cost='cost_price' if 'cost_price' in pc else ('cost' if 'cost' in pc else '0')
    rows=c.execute(f"SELECT id,{name},{price},{cost} FROM products ORDER BY {name},id").fetchall()
    out=[]
    for pid,n,p,co in rows:
        p=float(p or 0); co=float(co or 0); margin=((p-co)/p*100) if p else 0
        out.append((pid,n or '',p,co,margin))
    if own:c.close()
    return out

def scheduled_prices(conn=None, as_of=None):
    own=conn is None; c=conn or connect(); ensure_schema(c)
    d=as_of or datetime.now().strftime('%Y-%m-%d')
    pc=_cols(c,'products'); pname='description' if 'description' in pc else ('name' if 'name' in pc else "''")
    rows=c.execute(f"""SELECT ps.id,ps.product_id,COALESCE(p.{pname},''),ps.branch_id,
        ps.new_price,ps.effective_date,ps.end_date,ps.min_margin,ps.active,ps.reason
        FROM price_schedules ps LEFT JOIN products p ON p.id=ps.product_id
        ORDER BY ps.effective_date DESC,ps.id DESC""").fetchall()
    if own:c.close()
    return rows

def save_price_schedule(product_id, new_price, effective_date, end_date='', branch_id=None, min_margin=0, reason='', conn=None):
    datetime.strptime(effective_date,'%Y-%m-%d')
    if end_date: datetime.strptime(end_date,'%Y-%m-%d')
    if end_date and end_date < effective_date: raise ValueError('End date cannot be before effective date.')
    if float(new_price) < 0: raise ValueError('Price cannot be negative.')
    own = conn is None; c=conn or connect(); ensure_schema(c)
    # Margin protection is validated against current product cost when available.
    row=c.execute("SELECT cost_price FROM products WHERE id=?",(int(product_id),)).fetchone()
    if row and float(new_price)>0 and float(min_margin)>0:
        margin=(float(new_price)-float(row[0] or 0))/float(new_price)*100
        if margin + .0001 < float(min_margin): raise ValueError(f'Price violates minimum margin ({margin:.2f}% < {float(min_margin):.2f}%).')
    c.execute("INSERT INTO price_schedules(product_id,branch_id,new_price,effective_date,end_date,min_margin,reason) VALUES(?,?,?,?,?,?,?)",
              (int(product_id), branch_id if branch_id else None,float(new_price),effective_date,end_date or None,float(min_margin),reason.strip()))
    c.commit()
    if own: c.close()

def delete_price_schedule(schedule_id):
    c=connect(); ensure_schema(c); c.execute('DELETE FROM price_schedules WHERE id=?',(int(schedule_id),)); c.commit(); c.close()

def promotion_calendar(conn=None):
    own=conn is None; c=conn or connect(); ensure_schema(c)
    try: rows=c.execute("SELECT id,name,promo_type,value,start_date,end_date,min_spend,active,notes FROM promotions ORDER BY start_date,end_date,name").fetchall()
    except sqlite3.Error: rows=[]
    if own:c.close()
    return rows

def promotion_conflicts(conn=None):
    rows=promotion_calendar(conn); conflicts=[]
    for i,a in enumerate(rows):
        if not a[7]: continue
        for b in rows[i+1:]:
            if not b[7]: continue
            if a[5] >= b[4] and b[5] >= a[4]:
                conflicts.append((a[0],a[1],b[0],b[1],a[4],a[5],b[4],b[5]))
    return conflicts

def margin_alerts(conn=None, minimum_margin=10.0):
    return [r for r in pricing_catalog(conn) if r[4] < float(minimum_margin)]

def price_audit(conn=None, limit=200):
    own=conn is None; c=conn or connect(); ensure_schema(c)
    rows=c.execute("SELECT id,product_id,branch_id,old_price,new_price,changed_at,reason FROM price_change_audit ORDER BY id DESC LIMIT ?",(int(limit),)).fetchall()
    if own:c.close()
    return rows

def export_pricing(path, conn=None):
    rows=pricing_catalog(conn)
    with open(path,'w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['Product ID','Product','Selling Price','Cost','Margin %'])
        w.writerows(rows)

class AdvancedPricingWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); self.parent=parent; self.title('Advanced Pricing & Promotion Management'); self.geometry('1250x780'); self.minsize(1080,650); self.configure(bg='#eef2f7')
        ensure_schema(); self._build(); self.refresh()
    def _build(self):
        tk.Label(self,text='ADVANCED PRICING & PROMOTION MANAGEMENT',font=('Arial',18,'bold'),bg='#2c5282',fg='white',pady=12).pack(fill='x')
        bar=tk.Frame(self,bg='#eef2f7',pady=8); bar.pack(fill='x',padx=12)
        tk.Button(bar,text='REFRESH',command=self.refresh).pack(side='left',padx=4)
        tk.Button(bar,text='EXPORT PRICING CSV',command=self.export).pack(side='left',padx=4)
        tk.Label(bar,text=' Minimum margin %:',bg='#eef2f7').pack(side='left',padx=(18,3)); self.margin=tk.Entry(bar,width=7); self.margin.insert(0,'10'); self.margin.pack(side='left'); tk.Button(bar,text='CHECK MARGINS',command=self.refresh_catalog).pack(side='left',padx=4)
        self.alert=tk.Label(bar,text='',bg='#eef2f7',font=('Arial',10,'bold')); self.alert.pack(side='right',padx=8)
        self.nb=ttk.Notebook(self); self.nb.pack(fill='both',expand=True,padx=12,pady=(0,12))
        self.cat=tk.Frame(self.nb,bg='#eef2f7'); self.sched=tk.Frame(self.nb,bg='#eef2f7'); self.prom=tk.Frame(self.nb,bg='#eef2f7'); self.audit=tk.Frame(self.nb,bg='#eef2f7')
        self.nb.add(self.cat,text='Pricing & Margins'); self.nb.add(self.sched,text='Scheduled Prices'); self.nb.add(self.prom,text='Promotion Calendar'); self.nb.add(self.audit,text='Price Audit')
        self._catalog(); self._schedule(); self._promotions(); self._audit()
    def _tree(self,parent,cols,widths):
        t=ttk.Treeview(parent,columns=cols,show='headings')
        for c,w in zip(cols,widths): t.heading(c,text=c.replace('_',' ').title()); t.column(c,width=w,anchor='center')
        t.pack(fill='both',expand=True,padx=8,pady=8); return t
    def _catalog(self): self.ctree=self._tree(self.cat,('id','product','price','cost','margin'),(70,300,130,130,110))
    def _schedule(self):
        form=tk.Frame(self.sched,bg='#eef2f7',pady=7); form.pack(fill='x',padx=8); self.sf={}
        fields=[('product_id','Product ID'),('new_price','New Price'),('effective_date','Effective YYYY-MM-DD'),('end_date','End YYYY-MM-DD'),('branch_id','Branch ID'),('min_margin','Min Margin %'),('reason','Reason')]
        for i,(k,l) in enumerate(fields): tk.Label(form,text=l,bg='#eef2f7').grid(row=0,column=i,padx=3,sticky='w'); e=tk.Entry(form,width=16 if k!='reason' else 24); e.grid(row=1,column=i,padx=3); self.sf[k]=e
        tk.Button(form,text='SCHEDULE',command=self.save_schedule).grid(row=1,column=7,padx=5); tk.Button(form,text='DELETE SELECTED',command=self.delete_schedule).grid(row=1,column=8,padx=5)
        self.stree=self._tree(self.sched,('id','product_id','product','branch_id','new_price','effective','end','min_margin','active','reason'),(45,75,210,75,100,105,105,95,65,220))
    def _promotions(self):
        self.ptree=self._tree(self.prom,('id','name','type','value','start','end','min_spend','active','notes'),(50,210,120,80,105,105,100,65,260))
    def _audit(self): self.atree=self._tree(self.audit,('id','product_id','branch_id','old_price','new_price','changed_at','reason'),(50,90,90,110,110,170,300))
    def refresh_catalog(self):
        try: minimum=float(self.margin.get())
        except ValueError: minimum=10
        rows=pricing_catalog(); self.ctree.delete(*self.ctree.get_children())
        for r in rows:self.ctree.insert('', 'end',values=(r[0],r[1],f'R {r[2]:,.2f}',f'R {r[3]:,.2f}',f'{r[4]:.2f}%'))
        alerts=sum(r[4] < minimum for r in rows); self.alert.config(text=f'Margin alerts: {alerts}')
    def refresh_schedule(self):
        self.stree.delete(*self.stree.get_children())
        for r in scheduled_prices():self.stree.insert('', 'end',values=(r[0],r[1],r[2],r[3] or 'All',f'R {r[4]:,.2f}',r[5],r[6] or '',f'{r[7]:.2f}%', 'Yes' if r[8] else 'No',r[9] or ''))
    def refresh_promotions(self):
        self.ptree.delete(*self.ptree.get_children())
        for r in promotion_calendar():self.ptree.insert('', 'end',values=(r[0],r[1],r[2],r[3],r[4],r[5],f'R {r[6]:,.2f}','Yes' if r[7] else 'No',r[8] or ''))
        conflicts=promotion_conflicts(); self.alert.config(text=f'Promotion overlaps: {len(conflicts)}') if conflicts else None
    def refresh_audit(self):
        self.atree.delete(*self.atree.get_children()); [self.atree.insert('', 'end',values=r) for r in price_audit()]
    def refresh(self): self.refresh_catalog(); self.refresh_schedule(); self.refresh_promotions(); self.refresh_audit()
    def save_schedule(self):
        try: save_price_schedule(self.sf['product_id'].get(),self.sf['new_price'].get(),self.sf['effective_date'].get(),self.sf['end_date'].get(),self.sf['branch_id'].get() or None,self.sf['min_margin'].get() or 0,self.sf['reason'].get()); self.refresh_schedule(); messagebox.showinfo('Pricing','Price schedule saved.',parent=self)
        except Exception as e: messagebox.showerror('Pricing',str(e),parent=self)
    def delete_schedule(self):
        s=self.stree.selection()
        if s and messagebox.askyesno('Pricing','Delete selected price schedule?',parent=self): delete_price_schedule(self.stree.item(s[0],'values')[0]); self.refresh_schedule()
    def export(self):
        p=filedialog.asksaveasfilename(parent=self,defaultextension='.csv',filetypes=[('CSV files','*.csv')],initialfile='pricing_catalog.csv')
        if p:
            export_pricing(p); messagebox.showinfo('Export','Pricing catalog exported.',parent=self)
