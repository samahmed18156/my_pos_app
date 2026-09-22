"""Phase 18 - Backup & Disaster Recovery Upgrade.

from ui.window_polish import polish_window
Read-only recovery health plus safe verified backup/restore-drill operations.
No live business data is changed by the restore drill.
"""
from __future__ import annotations
import csv, os, sqlite3, tempfile, tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import ttk, messagebox
from core.config import DB_PATH, BACKUP_DIR
from services.production_hardening import backup_database, integrity_check, prune_backups


def _cleanup_failed_restore(target):
    try:
        os.remove(target)
    except OSError:
        return False
    return True

def backup_inventory(directory=BACKUP_DIR):
    p=Path(directory)
    if not p.exists(): return []
    rows=[]
    for f in p.glob('*.db'):
        try:
            rows.append({'path':str(f),'name':f.name,'size_bytes':f.stat().st_size,
                         'modified':datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                         'verified':integrity_check(f)})
        except OSError: rows.append({})
    return sorted(rows,key=lambda x:x['modified'],reverse=True)


def recovery_health(db_path=DB_PATH, backup_dir=BACKUP_DIR, max_age_hours=24):
    now=datetime.now(); inv=backup_inventory(backup_dir)
    newest=None
    if inv:
        newest=inv[0]
        age=(now-datetime.fromtimestamp(os.path.getmtime(newest['path']))).total_seconds()/3600
    db_ok=os.path.isfile(db_path) and integrity_check(db_path)
    verified=sum(1 for x in inv if x['verified'])
    disk_free=None
    try: disk_free=__import__('shutil').disk_usage(str(Path(db_path).parent)).free
    except OSError: disk_free=None
    return {'database_integrity':db_ok,'backup_count':len(inv),'verified_backups':verified,
            'newest_backup':newest['modified'] if newest else None,'newest_age_hours':age,
            'backup_current':bool(newest and newest['verified'] and age <= max_age_hours),
            'disk_free_bytes':disk_free,'status':'READY' if db_ok and newest and newest['verified'] and age <= max_age_hours else 'REVIEW'}


def restore_drill(backup_path, temp_dir=None):
    """Restore a backup into a temporary database and verify it, never live DB."""
    if not integrity_check(backup_path): raise ValueError('Backup failed SQLite integrity verification.')
    base=temp_dir or tempfile.gettempdir(); os.makedirs(base,exist_ok=True)
    fd,target=tempfile.mkstemp(prefix='bkpos_restore_drill_',suffix='.db',dir=base); os.close(fd)
    try:
        backup_database(backup_path,target)
        if not integrity_check(target): raise RuntimeError('Restore drill integrity verification failed.')
        con=sqlite3.connect(target)
        try: tables=int(con.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0])
        finally: con.close()
        return {'success':True,'tables':tables,'path':target}
    finally:
        try: os.remove(target)
        except OSError: _cleanup_failed_restore(target)


def export_inventory(rows,path):
    with open(path,'w',newline='',encoding='utf-8') as fh:
        w=csv.DictWriter(fh,fieldnames=['name','modified','size_bytes','verified']); w.writeheader()
        for r in rows: w.writerow({k:r[k] for k in w.fieldnames})
    return path


class BackupRecoveryUpgradeWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); polish_window(self); self.parent=parent; self.title('BKPOS Backup & Disaster Recovery Center'); self.geometry('1080x700'); self.minsize(900,580); self.configure(bg='#eef2f7'); self.transient(parent); self.grab_set(); self._build(); self.refresh()
    def _build(self):
        tk.Label(self,text='BACKUP & DISASTER RECOVERY',font=('Arial',19,'bold'),bg='#2c5282',fg='white',pady=12).pack(fill='x')
        tk.Label(self,text='Verified backups • recovery health • non-destructive restore drills • retention',bg='#eef2f7',font=('Arial',10)).pack(pady=10)
        bar=tk.Frame(self,bg='#eef2f7'); bar.pack(fill='x',padx=15)
        for text,cmd in [('REFRESH',self.refresh),('CREATE VERIFIED BACKUP',self.create_backup),('RUN RESTORE DRILL',self.drill),('PRUNE TO 30',self.prune),('EXPORT CSV',self.export)]: tk.Button(bar,text=text,command=cmd,font=('Arial',10,'bold')).pack(side='left',padx=4)
        self.tree=ttk.Treeview(self,columns=('name','modified','size','verified'),show='headings');
        for c,h,w in [('name','Backup',360),('modified','Modified',190),('size','Size',130),('verified','Integrity',140)]: self.tree.heading(c,text=h); self.tree.column(c,width=w)
        self.tree.pack(fill='both',expand=True,padx=15,pady=12)
        self.status=tk.Label(self,text='',bg='#eef2f7',font=('Arial',11,'bold'),anchor='w'); self.status.pack(fill='x',padx=15,pady=(0,12))
    def refresh(self):
        self.rows=backup_inventory(); self.tree.delete(*self.tree.get_children())
        for r in self.rows: self.tree.insert('','end',values=(r['name'],r['modified'],f"{r['size_bytes']/1024/1024:.2f} MB",'PASS' if r['verified'] else 'FAILED'))
        h=recovery_health(); age='n/a' if h['newest_age_hours'] is None else f"{h['newest_age_hours']:.1f}h"
        self.status.config(text=f"RECOVERY STATUS: {h['status']}  |  Backups: {h['backup_count']}  |  Verified: {h['verified_backups']}  |  Newest age: {age}")
    def create_backup(self):
        try:
            os.makedirs(BACKUP_DIR,exist_ok=True); stamp=datetime.now().strftime('%Y%m%d_%H%M%S'); target=os.path.join(BACKUP_DIR,f'pos_store_phase18_{stamp}.db'); backup_database(DB_PATH,target); self.refresh(); messagebox.showinfo('Backup',f'Verified backup created:\n{target}',parent=self)
        except Exception as exc: messagebox.showerror('Backup',str(exc),parent=self)
    def _selected(self):
        sel=self.tree.selection();
        if not sel: raise ValueError('Select a backup first.')
        return self.rows[self.tree.index(sel[0])]
    def drill(self):
        try:
            r=self._selected(); result=restore_drill(r['path']); messagebox.showinfo('Restore Drill',f"Restore drill passed.\nTables verified: {result['tables']}\n\nThe live database was not replaced.",parent=self)
        except Exception as exc: messagebox.showerror('Restore Drill',str(exc),parent=self)
    def prune(self):
        try: n=prune_backups(BACKUP_DIR,keep=30); self.refresh(); messagebox.showinfo('Retention',f'Removed {n} older backup(s).',parent=self)
        except Exception as exc: messagebox.showerror('Retention',str(exc),parent=self)
    def export(self):
        try:
            os.makedirs(BACKUP_DIR,exist_ok=True); path=os.path.join(BACKUP_DIR,'backup_inventory.csv'); export_inventory(self.rows,path); messagebox.showinfo('Export',f'Exported:\n{path}',parent=self)
        except Exception as exc: messagebox.showerror('Export',str(exc),parent=self)
