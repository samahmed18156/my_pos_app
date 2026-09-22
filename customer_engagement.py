"""BKPOS Phase 6: Customer Engagement & Promotions Center.

Management-facing customer segmentation and promotion catalogue.  The module
is intentionally read-only with respect to sales/accounting transactions.
Promotion records are definitions only; existing checkout pricing is unchanged.
"""
import csv
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta

from core.config import DB_PATH

DB_NAME = DB_PATH


def connect():
    return sqlite3.connect(DB_NAME)


def ensure_schema(conn=None):
    own = conn is None
    c = conn or connect()
    c.execute("""CREATE TABLE IF NOT EXISTS promotions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        promo_type TEXT NOT NULL DEFAULT 'Percentage',
        value REAL NOT NULL DEFAULT 0,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        min_spend REAL NOT NULL DEFAULT 0,
        active INTEGER NOT NULL DEFAULT 1,
        notes TEXT DEFAULT '',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_promotions_dates ON promotions(active,start_date,end_date)")
    if own:
        c.commit()
        c.close()


def customer_segments(conn=None, start_date=None, end_date=None):
    """Return customer segments from completed, non-voided sales.

    Segment rules: VIP >= R10,000, Loyal >= R3,000, Active >= R500,
    New/Occasional > 0, Inactive = no qualifying sales in the period.
    """
    own = conn is None
    c = conn or connect()
    ensure_schema(c)
    params = []
    where = "COALESCE(s.voided,0)=0 AND COALESCE(s.status,'COMPLETED')='COMPLETED' AND s.customer_id IS NOT NULL"
    if start_date:
        where += " AND date(s.timestamp)>=?"; params.append(start_date)
    if end_date:
        where += " AND date(s.timestamp)<=?"; params.append(end_date)
    rows = c.execute(f"""
        SELECT cu.id, cu.name, COALESCE(cu.phone,''), COUNT(s.id),
               COALESCE(SUM(s.total_amount),0), MAX(s.timestamp)
        FROM customers cu
        LEFT JOIN sales_history s ON s.customer_id=cu.id AND {where}
        WHERE COALESCE(cu.active,1)=1
        GROUP BY cu.id,cu.name,cu.phone
        ORDER BY COALESCE(SUM(s.total_amount),0) DESC, cu.name
    """, params).fetchall()
    out=[]
    for cid,name,phone,txns,spend,last_sale in rows:
        spend=float(spend or 0); txns=int(txns or 0)
        if spend >= 10000: segment='VIP'
        elif spend >= 3000: segment='Loyal'
        elif spend >= 500: segment='Active'
        elif spend > 0: segment='Occasional'
        else: segment='Inactive'
        points=int(spend // 10)
        out.append(dict(id=cid,name=name,phone=phone,transactions=txns,spend=spend,last_sale=last_sale or '',segment=segment,points=points))
    if own: c.close()
    return out


def promotion_rows(conn=None, active_only=False):
    own=conn is None; c=conn or connect(); ensure_schema(c)
    sql="SELECT id,name,promo_type,value,start_date,end_date,min_spend,active,notes FROM promotions"
    if active_only: sql += " WHERE active=1"
    sql += " ORDER BY start_date DESC,id DESC"
    rows=c.execute(sql).fetchall()
    if own: c.close()
    return rows


def save_promotion(name,promo_type,value,start_date,end_date,min_spend=0,active=1,notes=''):
    datetime.strptime(start_date,'%Y-%m-%d'); datetime.strptime(end_date,'%Y-%m-%d')
    if datetime.strptime(end_date,'%Y-%m-%d') < datetime.strptime(start_date,'%Y-%m-%d'):
        raise ValueError('Promotion end date cannot be before the start date.')
    if float(value) < 0 or float(min_spend) < 0: raise ValueError('Promotion values cannot be negative.')
    c=connect(); ensure_schema(c)
    c.execute("""INSERT INTO promotions(name,promo_type,value,start_date,end_date,min_spend,active,notes)
                 VALUES(?,?,?,?,?,?,?,?)
                 ON CONFLICT(name) DO UPDATE SET promo_type=excluded.promo_type,value=excluded.value,
                 start_date=excluded.start_date,end_date=excluded.end_date,min_spend=excluded.min_spend,
                 active=excluded.active,notes=excluded.notes""",
              (name.strip(),promo_type,float(value),start_date,end_date,float(min_spend),int(bool(active)),notes.strip()))
    c.commit(); c.close()


def delete_promotion(promotion_id):
    c=connect(); ensure_schema(c); c.execute('DELETE FROM promotions WHERE id=?',(int(promotion_id),)); c.commit(); c.close()


class CustomerEngagementWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); self.parent=parent
        self.title('Customer Engagement & Promotions'); self.geometry('1220x760'); self.minsize(1050,620)
        self.configure(bg='#eef2f7'); ensure_schema(); self._build(); self.refresh()

    def _build(self):
        tk.Label(self,text='CUSTOMER ENGAGEMENT & PROMOTIONS',font=('Arial',18,'bold'),bg='#2c5282',fg='white',pady=12).pack(fill='x')
        bar=tk.Frame(self,bg='#eef2f7',pady=10); bar.pack(fill='x',padx=12)
        today=datetime.now().date(); self.frm=tk.Entry(bar,width=12); self.frm.insert(0,(today-timedelta(days=30)).isoformat()); self.frm.pack(side='left')
        tk.Label(bar,text='  To',bg='#eef2f7').pack(side='left'); self.to=tk.Entry(bar,width=12); self.to.insert(0,today.isoformat()); self.to.pack(side='left',padx=5)
        tk.Button(bar,text='REFRESH',command=self.refresh,font=('Arial',10,'bold')).pack(side='left',padx=6)
        tk.Button(bar,text='EXPORT CUSTOMERS',command=self.export_customers).pack(side='left',padx=4)
        self.nb=ttk.Notebook(self); self.nb.pack(fill='both',expand=True,padx=12,pady=(0,12))
        self.customer_tab=tk.Frame(self.nb,bg='#eef2f7'); self.nb.add(self.customer_tab,text='Customer Segments')
        self.promo_tab=tk.Frame(self.nb,bg='#eef2f7'); self.nb.add(self.promo_tab,text='Promotions')
        self._build_customers(); self._build_promos()

    def _build_customers(self):
        self.summary=tk.Label(self.customer_tab,text='',font=('Arial',12,'bold'),bg='#eef2f7',anchor='w'); self.summary.pack(fill='x',padx=8,pady=8)
        cols=('id','name','phone','segment','transactions','spend','points','last')
        self.tree=ttk.Treeview(self.customer_tab,columns=cols,show='headings')
        heads={'id':'ID','name':'Customer','phone':'Phone','segment':'Segment','transactions':'Txns','spend':'Spend (R)','points':'Points*','last':'Last Sale'}
        for col in cols: self.tree.heading(col,text=heads[col]); self.tree.column(col,width={'id':55,'name':220,'phone':130,'segment':110,'transactions':70,'spend':110,'points':85,'last':150}[col],anchor='e' if col in ('transactions','spend','points') else 'center')
        self.tree.pack(fill='both',expand=True,padx=8,pady=8)
        tk.Label(self.customer_tab,text='* Points are an analytics estimate (1 point per R10 completed sale spend); no existing checkout balance is changed.',bg='#eef2f7',fg='#555').pack(anchor='w',padx=8,pady=(0,8))

    def _build_promos(self):
        form=tk.Frame(self.promo_tab,bg='#eef2f7',pady=8); form.pack(fill='x',padx=8)
        self.fields={}
        labels=[('name','Name'),('promo_type','Type'),('value','Value'),('start_date','Start'),('end_date','End'),('min_spend','Min Spend'),('notes','Notes')]
        for i,(key,label) in enumerate(labels):
            tk.Label(form,text=label,bg='#eef2f7').grid(row=0,column=i,sticky='w',padx=3)
            if key=='promo_type': w=ttk.Combobox(form,values=('Percentage','Fixed Amount','Buy X Get Y'),state='readonly',width=14); w.set('Percentage')
            else: w=tk.Entry(form,width=16 if key!='notes' else 28)
            w.grid(row=1,column=i,padx=3,pady=3); self.fields[key]=w
        tk.Button(form,text='SAVE / UPDATE',command=self.save_promo,font=('Arial',9,'bold')).grid(row=1,column=7,padx=5)
        tk.Button(form,text='DELETE SELECTED',command=self.delete_selected).grid(row=1,column=8,padx=5)
        cols=('id','name','type','value','start','end','min','active','notes'); self.ptree=ttk.Treeview(self.promo_tab,columns=cols,show='headings')
        heads={'id':'ID','name':'Name','type':'Type','value':'Value','start':'Start','end':'End','min':'Min Spend','active':'Active','notes':'Notes'}
        widths={'id':50,'name':190,'type':120,'value':80,'start':100,'end':100,'min':100,'active':70,'notes':260}
        for col in cols: self.ptree.heading(col,text=heads[col]); self.ptree.column(col,width=widths[col],anchor='center')
        self.ptree.pack(fill='both',expand=True,padx=8,pady=8); self.ptree.bind('<Double-1>',self.load_promo)

    def refresh(self):
        try: datetime.strptime(self.frm.get(),'%Y-%m-%d'); datetime.strptime(self.to.get(),'%Y-%m-%d')
        except ValueError: messagebox.showerror('Customer Engagement','Dates must use YYYY-MM-DD.',parent=self); return
        rows=customer_segments(start_date=self.frm.get(),end_date=self.to.get()); self.tree.delete(*self.tree.get_children())
        for r in rows: self.tree.insert('', 'end', values=(r['id'],r['name'],r['phone'],r['segment'],r['transactions'],f"R {r['spend']:,.2f}",r['points'],r['last_sale']))
        active=sum(r['segment']!='Inactive' for r in rows); spend=sum(r['spend'] for r in rows); self.summary.config(text=f'Customers: {len(rows)}   |   Active buyers: {active}   |   Spend: R {spend:,.2f}   |   Loyalty points (estimated): {sum(r["points"] for r in rows):,}')
        self._refresh_promos()

    def _refresh_promos(self):
        self.ptree.delete(*self.ptree.get_children())
        for r in promotion_rows(): self.ptree.insert('', 'end',values=(r[0],r[1],r[2],f'{float(r[3]):g}',r[4],r[5],f'R {float(r[6]):,.2f}', 'Yes' if r[7] else 'No',r[8] or ''))

    def save_promo(self):
        try:
            save_promotion(*(self.fields[k].get() for k in ('name','promo_type','value','start_date','end_date','min_spend')),active=1,notes=self.fields['notes'].get())
            self._refresh_promos(); messagebox.showinfo('Promotions','Promotion saved.',parent=self)
        except Exception as exc: messagebox.showerror('Promotions',str(exc),parent=self)

    def load_promo(self,_event=None):
        sel=self.ptree.selection()
        if not sel:return
        vals=self.ptree.item(sel[0],'values')
        for key,val in zip(('name','promo_type','value','start_date','end_date','min_spend','notes'),(vals[1],vals[2],vals[3],vals[4],vals[5],vals[6].replace('R ', '').replace(',',''),vals[8])):
            self.fields[key].delete(0,'end'); self.fields[key].insert(0,val)

    def delete_selected(self):
        sel=self.ptree.selection()
        if not sel:return
        if not messagebox.askyesno('Promotions','Delete the selected promotion definition?',parent=self): return
        delete_promotion(self.ptree.item(sel[0],'values')[0]); self._refresh_promos()

    def export_customers(self):
        path=filedialog.asksaveasfilename(parent=self,defaultextension='.csv',filetypes=[('CSV files','*.csv')],initialfile='customer_segments.csv')
        if not path:return
        rows=customer_segments(start_date=self.frm.get(),end_date=self.to.get())
        with open(path,'w',newline='',encoding='utf-8') as f:
            w=csv.writer(f); w.writerow(['ID','Customer','Phone','Segment','Transactions','Spend','Estimated Points','Last Sale'])
            for r in rows:w.writerow([r['id'],r['name'],r['phone'],r['segment'],r['transactions'],f"{r['spend']:.2f}",r['points'],r['last_sale']])
        messagebox.showinfo('Export','Customer segmentation exported.',parent=self)
