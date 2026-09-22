"""BKPOS Phase 16 — Automated Alerts & Management Notifications.

Read-only alert aggregation. It evaluates existing operational data and stores
acknowledgement state separately; it never posts, edits, or reverses business data.
"""
import csv, sqlite3, tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, timedelta
from core.config import DB_PATH


def connect(): return sqlite3.connect(DB_PATH, timeout=10)

def ensure_schema(conn=None):
    own=conn is None; c=conn or connect()
    c.execute("""CREATE TABLE IF NOT EXISTS management_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT, alert_key TEXT NOT NULL UNIQUE,
        category TEXT NOT NULL, severity TEXT NOT NULL, title TEXT NOT NULL,
        detail TEXT DEFAULT '', amount REAL DEFAULT 0, status TEXT NOT NULL DEFAULT 'OPEN',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP, acknowledged_at DATETIME)""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_management_alerts_status ON management_alerts(status,severity)")
    if own: c.commit(); c.close()

def _exists(c,t): return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(t,)).fetchone() is not None

def generate_alerts(conn=None, as_of=None):
    own=conn is None; c=conn or connect(); ensure_schema(c); out=[]; today=as_of or datetime.now().strftime('%Y-%m-%d')
    if _exists(c,'products'):
        cols={r[1] for r in c.execute('PRAGMA table_info(products)')}
        stock='soh' if 'soh' in cols else None; reorder='reorder_level' if 'reorder_level' in cols else ('min_stock' if 'min_stock' in cols else None)
        if stock:
            name_expr='description' if 'description' in cols else ('name' if 'name' in cols else "''")
            q=f"SELECT id,COALESCE({name_expr},''),COALESCE({stock},0)" + (f",COALESCE({reorder},0)" if reorder else "") + " FROM products"
            for r in c.execute(q).fetchall():
                pid,name,soh,*rest=r; threshold=float(rest[0]) if rest else 0
                if float(soh or 0)<0: out.append((f'NEG_STOCK:{pid}','Inventory','HIGH',f'Negative stock: {name}',f'SOH {float(soh):g}',0))
                elif reorder and float(soh or 0)<=threshold: out.append((f'LOW_STOCK:{pid}','Inventory','MEDIUM',f'Low stock: {name}',f'SOH {float(soh):g} / minimum {threshold:g}',0))
    if _exists(c,'cashier_shifts'):
        for sid,cashier,diff in c.execute("SELECT id,cashier,COALESCE(difference,0) FROM cashier_shifts WHERE status='OPEN'").fetchall():
            out.append((f'OPEN_SHIFT:{sid}','Cash','HIGH',f'Open cashier shift: {cashier}',f'Shift #{sid} remains open',0))
        for sid,cashier,diff in c.execute("SELECT id,cashier,COALESCE(difference,0) FROM cashier_shifts WHERE status<>'OPEN' AND ABS(COALESCE(difference,0))>0.01 ORDER BY id DESC LIMIT 50").fetchall():
            out.append((f'CASH_VARIANCE:{sid}','Cash','HIGH',f'Cash variance: {cashier}',f'Shift #{sid} variance R {float(diff):,.2f}',float(diff)))
    if _exists(c,'sales_history'):
        row=c.execute("SELECT COUNT(*),COALESCE(SUM(total_amount),0) FROM sales_history WHERE date(timestamp)=? AND COALESCE(voided,0)=1",(today,)).fetchone()
        if row[0]: out.append((f'VOIDS:{today}','Sales','MEDIUM','Voided sales today',f'{row[0]} voided sale(s)',float(row[1] or 0)))
    if _exists(c,'audit_log'):
        n=c.execute("SELECT COUNT(*) FROM audit_log WHERE date(event_time)=? AND event_type='LOGIN_FAILED'",(today,)).fetchone()[0]
        if n>=3: out.append((f'FAILED_LOGINS:{today}','Security','HIGH','Repeated failed logins',f'{n} failed login event(s) today',0))
    if _exists(c,'staged_conflicts'):
        n=c.execute('SELECT COUNT(*) FROM staged_conflicts').fetchone()[0]
        if n: out.append(('SYNC_CONFLICTS','Branches','HIGH','Branch synchronization conflicts',f'{n} staged conflict(s) require review',0))
    for key,cat,sev,title,detail,amt in out:
        c.execute("INSERT INTO management_alerts(alert_key,category,severity,title,detail,amount) VALUES(?,?,?,?,?,?) ON CONFLICT(alert_key) DO UPDATE SET category=excluded.category,severity=excluded.severity,title=excluded.title,detail=excluded.detail,amount=excluded.amount",(key,cat,sev,title,detail,amt))
    if own:c.commit();c.close()
    return out

def list_alerts(conn=None, status='OPEN'):
    own=conn is None;c=conn or connect();ensure_schema(c);generate_alerts(c)
    rows=c.execute("SELECT id,alert_key,category,severity,title,detail,amount,status,created_at,acknowledged_at FROM management_alerts WHERE status=? ORDER BY CASE severity WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END, id DESC",(status,)).fetchall()
    if own:c.close()
    return rows

def acknowledge_alert(alert_id, conn=None):
    own=conn is None;c=conn or connect();ensure_schema(c);c.execute("UPDATE management_alerts SET status='ACKNOWLEDGED',acknowledged_at=CURRENT_TIMESTAMP WHERE id=?",(int(alert_id),));c.commit();
    if own:c.close()

def alert_summary(conn=None):
    rows=list_alerts(conn); return {'total':len(rows),'high':sum(r[3]=='HIGH' for r in rows),'medium':sum(r[3]=='MEDIUM' for r in rows),'inventory':sum(r[2]=='Inventory' for r in rows),'cash':sum(r[2]=='Cash' for r in rows)}

class AutomatedAlertsWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent);self.parent=parent;self.title('BKPOS Automated Alerts & Management Notifications');self.geometry('1220x720');self.transient(parent);self.grab_set();self._build();self.refresh()
    def _build(self):
        tk.Label(self,text='AUTOMATED ALERTS & MANAGEMENT NOTIFICATIONS',font=('Segoe UI',18,'bold'),bg='#2c5282',fg='white',pady=13).pack(fill='x')
        bar=tk.Frame(self,pady=8);bar.pack(fill='x',padx=15);tk.Button(bar,text='REFRESH ALERTS',command=self.refresh).pack(side='left');tk.Button(bar,text='ACKNOWLEDGE SELECTED',command=self.ack).pack(side='left',padx=6);tk.Button(bar,text='EXPORT CSV',command=self.export).pack(side='left');self.status=tk.Label(bar,text='');self.status.pack(side='left',padx=12)
        cards=tk.Frame(self);cards.pack(fill='x',padx=15);self.cards={}
        for i,k in enumerate(('Open Alerts','High Risk','Medium Risk','Inventory','Cash')):
            f=tk.Frame(cards,bd=1,relief='solid');f.grid(row=0,column=i,padx=4,sticky='nsew');cards.grid_columnconfigure(i,weight=1);tk.Label(f,text=k,font=('Segoe UI',9,'bold')).pack(pady=(8,2));v=tk.Label(f,text='—',font=('Segoe UI',14,'bold'));v.pack(pady=(0,8));self.cards[k]=v
        fr=tk.Frame(self);fr.pack(fill='both',expand=True,padx=15,pady=10);self.tree=ttk.Treeview(fr,columns=('severity','category','title','detail','amount','created'),show='headings',selectmode='browse')
        for c,h,w in (('severity','Severity',90),('category','Category',120),('title','Alert',280),('detail','Detail',430),('amount','Amount',120),('created','Created',160)):self.tree.heading(c,text=h);self.tree.column(c,width=w,anchor='e' if c=='amount' else 'w')
        self.tree.pack(fill='both',expand=True)
    def refresh(self):
        try:
            s=alert_summary();rows=list_alerts();self.tree.delete(*self.tree.get_children())
            for r in rows:self.tree.insert('','end',iid=str(r[0]),values=(r[3],r[2],r[4],r[5],f'R {r[6]:,.2f}' if r[6] else '—',r[8]))
            for k,v in (('Open Alerts',s['total']),('High Risk',s['high']),('Medium Risk',s['medium']),('Inventory',s['inventory']),('Cash',s['cash'])):self.cards[k].config(text=str(v))
            self.status.config(text='Read-only monitoring | acknowledgement only')
        except Exception as e:messagebox.showerror('Automated Alerts',str(e),parent=self)
    def ack(self):
        sel=self.tree.selection()
        if not sel:return
        acknowledge_alert(int(sel[0]));self.refresh()
    def export(self):
        p=filedialog.asksaveasfilename(parent=self,defaultextension='.csv',filetypes=(('CSV files','*.csv'),),initialfile='management_alerts.csv')
        if not p:return
        with open(p,'w',newline='',encoding='utf-8-sig') as f:
            w=csv.writer(f);w.writerow(['Severity','Category','Alert','Detail','Amount','Status','Created']);
            for r in list_alerts():w.writerow([r[3],r[2],r[4],r[5],r[6],r[7],r[8]])
        messagebox.showinfo('Automated Alerts','CSV exported successfully.',parent=self)
