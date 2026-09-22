from core.logger import logger as _bkpos_logger

import sqlite3, tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from core.config import DB_PATH
from core.audit_log import ensure_audit_table
DB_NAME=DB_PATH

def ensure_schema():
    """Ensure the canonical audit table plus legacy UI compatibility fields."""
    c = sqlite3.connect(DB_NAME)
    try:
        ensure_audit_table(c)
        c.execute("CREATE TRIGGER IF NOT EXISTS trg_audit_log_no_update BEFORE UPDATE ON audit_log BEGIN SELECT RAISE(ABORT, 'Audit log is append-only'); END")
        c.execute("CREATE TRIGGER IF NOT EXISTS trg_audit_log_no_delete BEFORE DELETE ON audit_log BEGIN SELECT RAISE(ABORT, 'Audit log is append-only'); END")
        c.commit()
    finally:
        c.close()

def log_action(username, action, entity_type="", entity_id="", details="", role="", branch_id=1):
    try:
        ensure_schema(); c=sqlite3.connect(DB_NAME)
        c.execute("INSERT INTO audit_log(event_time,username,role,action,entity_type,entity_id,details,branch_id,event_type) VALUES(datetime('now','localtime'),?,?,?,?,?,?,?,?)",
                  (username or "Unknown",role or "",action,entity_type,str(entity_id or ""),details,branch_id or 1,action))
        c.commit(); c.close()
    except Exception as exc:
        _bkpos_logger.warning("Suppressed exception in audit_log.py", exc_info=exc)

class AuditLogWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent); self.parent=parent
        self.title("Audit Log"); self.geometry("1180x680"); self.configure(bg="#eef2f7")
        ensure_schema(); self.build(); self.refresh()
    def build(self):
        tk.Label(self,text="AUDIT LOG — WHO DID WHAT",font=("Arial",19,"bold"),bg="#2c5282",fg="white",pady=12).pack(fill="x")
        f=tk.Frame(self,bg="#eef2f7",padx=12,pady=10); f.pack(fill="x")
        tk.Label(f,text="Search:",bg="#eef2f7",font=("Arial",10,"bold")).pack(side="left")
        self.q=tk.Entry(f,width=38,font=("Arial",11)); self.q.pack(side="left",padx=7); self.q.bind("<KeyRelease>",lambda e:self.refresh())
        tk.Button(f,text="Refresh",command=self.refresh).pack(side="left")
        cols=("time","user","role","action","entity","id","details","branch")
        self.tree=ttk.Treeview(self,columns=cols,show="headings")
        heads={"time":"Date / Time","user":"User","role":"Role","action":"Action","entity":"Entity","id":"ID","details":"Details","branch":"Branch"}
        widths={"time":145,"user":100,"role":80,"action":150,"entity":100,"id":80,"details":400,"branch":70}
        for x in cols:self.tree.heading(x,text=heads[x]);self.tree.column(x,width=widths[x],anchor="w")
        self.tree.pack(fill="both",expand=True,padx=12,pady=5)
    def refresh(self):
        q=self.q.get().strip() if hasattr(self,"q") else ""
        c=sqlite3.connect(DB_NAME)
        rows=c.execute("""SELECT timestamp,username,role,action,entity_type,entity_id,details,branch_id
                          FROM audit_log WHERE username LIKE ? OR action LIKE ? OR details LIKE ? OR entity_type LIKE ?
                          ORDER BY id DESC LIMIT 1000""",(f"%{q}%",f"%{q}%",f"%{q}%",f"%{q}%")).fetchall();c.close()
        for i in self.tree.get_children():self.tree.delete(i)
        for r in rows:self.tree.insert("", "end",values=r)
