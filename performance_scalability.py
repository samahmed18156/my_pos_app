"""Phase 19 - Performance & Scalability Center.

Read-only diagnostics with an optional additive index optimizer. Existing business
workflows are untouched; no records are deleted or rewritten.
"""
from __future__ import annotations
import csv, os, sqlite3, tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk, messagebox
from core.config import DB_PATH

RECOMMENDED_INDEXES = [
    ("idx_sales_history_timestamp_status", "sales_history", "timestamp, status"),
    ("idx_sales_history_branch_timestamp", "sales_history", "branch_id, timestamp"),
    ("idx_sales_history_voided_status", "sales_history", "voided, status"),
    ("idx_sale_items_sale_id", "sale_items", "sale_id"),
    ("idx_sale_items_barcode", "sale_items", "barcode"),
    ("idx_return_history_timestamp", "return_history", "timestamp"),
    ("idx_return_items_return_id", "return_items", "return_id"),
    ("idx_cashier_shifts_opened", "cashier_shifts", "opened_at"),
    ("idx_cashier_shifts_status", "cashier_shifts", "status"),
    ("idx_products_barcode", "products", "barcode"),
    ("idx_products_active_soh", "products", "active, soh"),
    ("idx_audit_log_timestamp", "audit_log", "timestamp"),
    ("idx_audit_log_user_timestamp", "audit_log", "user_id, timestamp"),
]

def _tables(con):
    return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}

def index_inventory(db_path=DB_PATH):
    if not os.path.isfile(db_path): return []
    con=sqlite3.connect(db_path)
    try:
        existing={r[1]: r for r in con.execute("PRAGMA index_list('sales_history')")}
        rows=[]
        for name,table,columns in RECOMMENDED_INDEXES:
            present=False
            try:
                present=con.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",(name,)).fetchone() is not None
            except sqlite3.DatabaseError as exc:
                _ = exc
            rows.append({'name':name,'table':table,'columns':columns,'present':present,
                         'applicable':table in _tables(con)})
        return rows
    finally: con.close()

def optimize_indexes(db_path=DB_PATH):
    """Create only missing, applicable indexes; never modifies business rows."""
    if not os.path.isfile(db_path): return {'created':0,'skipped':len(RECOMMENDED_INDEXES)}
    con=sqlite3.connect(db_path)
    created=0; skipped=0
    try:
        tables=_tables(con)
        for name,table,columns in RECOMMENDED_INDEXES:
            if table not in tables: skipped += 1; continue
            exists=con.execute("SELECT 1 FROM sqlite_master WHERE type='index' AND name=?",(name,)).fetchone()
            if exists: skipped += 1; continue
            con.execute(f'CREATE INDEX IF NOT EXISTS "{name}" ON "{table}" ({columns})')
            created += 1
        con.commit()
        return {'created':created,'skipped':skipped}
    finally: con.close()

def database_metrics(db_path=DB_PATH):
    if not os.path.isfile(db_path): return {'exists':False,'size_bytes':0,'tables':0,'indexes':0,'rows':0,'integrity':'MISSING'}
    con=sqlite3.connect(db_path)
    try:
        tables=con.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        indexes=con.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'").fetchone()[0]
        rows=0
        for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            try: rows += int(con.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0])
            except sqlite3.DatabaseError as exc:
                _ = exc
        integrity=con.execute('PRAGMA integrity_check').fetchone()[0]
        return {'exists':True,'size_bytes':os.path.getsize(db_path),'tables':tables,'indexes':indexes,'rows':rows,'integrity':integrity}
    finally: con.close()

def query_plan(db_path=DB_PATH, sql='SELECT id FROM sales_history WHERE status=? AND timestamp BETWEEN ? AND ?'):
    if not os.path.isfile(db_path): return []
    con=sqlite3.connect(db_path)
    try:
        return [tuple(r) for r in con.execute('EXPLAIN QUERY PLAN '+sql, ('COMPLETED','2000-01-01','2099-12-31')).fetchall()]
    except sqlite3.DatabaseError as exc:
        return [('ERROR',str(exc))]
    finally: con.close()

def export_indexes(rows,path):
    with open(path,'w',newline='',encoding='utf-8') as fh:
        w=csv.DictWriter(fh,fieldnames=['name','table','columns','present','applicable']); w.writeheader(); w.writerows(rows)
    return path

class PerformanceScalabilityWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); self.parent=parent; self.title('BKPOS Performance & Scalability Center'); self.geometry('1120x720'); self.minsize(900,580); self._build(); self.refresh()
    def _build(self):
        tk.Label(self,text='PERFORMANCE & SCALABILITY',font=('Arial',19,'bold'),bg='#2c5282',fg='white',pady=12).pack(fill='x')
        tk.Label(self,text='Database health • index coverage • query-plan diagnostics • additive optimization',font=('Arial',10)).pack(pady=10)
        bar=tk.Frame(self); bar.pack(fill='x',padx=15)
        for text,cmd in [('REFRESH',self.refresh),('OPTIMIZE INDEXES',self.optimize),('EXPORT CSV',self.export)]: tk.Button(bar,text=text,command=cmd,font=('Arial',10,'bold')).pack(side='left',padx=4)
        self.kpi=tk.Label(self,text='',font=('Arial',11,'bold'),anchor='w'); self.kpi.pack(fill='x',padx=15,pady=10)
        self.tree=ttk.Treeview(self,columns=('name','table','columns','present','applicable'),show='headings')
        for c,h,w in [('name','Index',270),('table','Table',180),('columns','Columns',260),('present','Present',100),('applicable','Applicable',110)]: self.tree.heading(c,text=h); self.tree.column(c,width=w)
        self.tree.pack(fill='both',expand=True,padx=15,pady=10)
        self.status=tk.Label(self,text='',anchor='w',font=('Arial',10,'bold')); self.status.pack(fill='x',padx=15,pady=(0,12))
    def refresh(self):
        self.rows=index_inventory(); self.tree.delete(*self.tree.get_children());
        for r in self.rows: self.tree.insert('','end',values=(r['name'],r['table'],r['columns'],'YES' if r['present'] else 'NO','YES' if r['applicable'] else 'N/A'))
        m=database_metrics(); applicable=sum(r['applicable'] for r in self.rows); covered=sum(r['present'] and r['applicable'] for r in self.rows)
        self.kpi.config(text=f"DB: {m['size_bytes']/1024/1024:.2f} MB | Tables: {m['tables']} | Rows: {m['rows']:,} | Indexes: {m['indexes']} | Coverage: {covered}/{applicable} | Integrity: {m['integrity']}")
        plan=query_plan(); detail='; '.join(str(x[-1]) for x in plan[:2]); self.status.config(text='QUERY PLAN: '+detail)
    def optimize(self):
        try:
            result=optimize_indexes(); self.refresh(); messagebox.showinfo('Performance Optimization',f"Created {result['created']} missing index(es).\nSkipped: {result['skipped']}.\n\nNo business rows were changed.",parent=self)
        except Exception as exc: messagebox.showerror('Performance Optimization',str(exc),parent=self)
    def export(self):
        try:
            path=os.path.join(Path(DB_PATH).parent,'performance_index_inventory.csv'); export_indexes(self.rows,path); messagebox.showinfo('Export',f'Exported:\n{path}',parent=self)
        except Exception as exc: messagebox.showerror('Export',str(exc),parent=self)
