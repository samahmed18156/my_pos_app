from core.logger import logger as _bkpos_logger

import sqlite3, tkinter as tk
from tkinter import ttk, messagebox
from core.config import DB_PATH
DB_NAME=DB_PATH
def ensure_schema():
    c=sqlite3.connect(DB_NAME);cur=c.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS branch_stock(
      branch_id INTEGER,barcode TEXT,soh REAL DEFAULT 0,PRIMARY KEY(branch_id,barcode))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS stock_transfers(
      id INTEGER PRIMARY KEY AUTOINCREMENT,transfer_no TEXT,from_branch INTEGER,to_branch INTEGER,
      barcode TEXT,description TEXT,qty REAL,status TEXT DEFAULT 'POSTED',cashier TEXT,
      timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    branches=cur.execute("SELECT id FROM branches").fetchall()
    products=cur.execute("SELECT barcode,soh FROM products").fetchall()
    for bid, in branches:
        for code,soh in products:
            cur.execute("INSERT OR IGNORE INTO branch_stock(branch_id,barcode,soh) VALUES(?,?,?)",(bid,code,soh if bid==1 else 0))
    c.commit();c.close()
class BranchTransferWindow(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent);self.parent=parent;self.title("Branch Stock Transfers");self.geometry("1050x650");self.configure(bg="#eef2f7");ensure_schema();self.build();self.refresh()
    def build(self):
        tk.Label(self,text="BRANCH STOCK TRANSFERS",font=("Arial",19,"bold"),bg="#2c5282",fg="white",pady=12).pack(fill="x")
        f=tk.Frame(self,bg="#eef2f7",pady=10);f.pack(fill="x")
        c=sqlite3.connect(DB_NAME);self.branches=c.execute("SELECT id,name FROM branches ORDER BY id").fetchall();c.close()
        tk.Label(f,text="From",bg="#eef2f7").pack(side="left");self.frm=ttk.Combobox(f,values=[f"{i}: {n}" for i,n in self.branches],state="readonly",width=20);self.frm.pack(side="left",padx=5)
        tk.Label(f,text="To",bg="#eef2f7").pack(side="left");self.to=ttk.Combobox(f,values=[f"{i}: {n}" for i,n in self.branches],state="readonly",width=20);self.to.pack(side="left",padx=5)
        self.frm.current(0);self.to.current(1 if len(self.branches)>1 else 0)
        tk.Label(f,text="Barcode",bg="#eef2f7").pack(side="left");self.code=tk.Entry(f,width=18);self.code.pack(side="left",padx=5)
        tk.Label(f,text="Qty",bg="#eef2f7").pack(side="left");self.qty=tk.Entry(f,width=8);self.qty.pack(side="left",padx=5)
        tk.Button(f,text="POST TRANSFER",command=self.post).pack(side="left",padx=8)
        cols=("no","from","to","barcode","description","qty","status","cashier","time");self.tree=ttk.Treeview(self,columns=cols,show="headings")
        for c,h,w in [("no","Transfer",100),("from","From",100),("to","To",100),("barcode","Barcode",150),("description","Description",260),("qty","Qty",70),("status","Status",90),("cashier","Cashier",100),("time","Time",150)]:self.tree.heading(c,text=h);self.tree.column(c,width=w)
        self.tree.pack(fill="both",expand=True,padx=15,pady=8)
    def post(self):
        try:fr=int(self.frm.get().split(":")[0]);to=int(self.to.get().split(":")[0]);q=float(self.qty.get());code=self.code.get().strip()
        except:messagebox.showerror("Transfer","Enter valid branches, barcode and quantity.",parent=self);return
        if fr==to or q<=0:messagebox.showwarning("Transfer","Choose different branches and a positive quantity.",parent=self);return
        c=sqlite3.connect(DB_NAME)
        try:
            from services.branch_stock_service import ensure_schema as ensure_branch_stock, transfer
            ensure_branch_stock(c)
            no, before, after = transfer(c, fr, to, code, q, getattr(self.parent,"cashier_username","Unknown"))
            c.commit()
        except Exception as exc:
            c.rollback();c.close();messagebox.showerror("Transfer",str(exc),parent=self);return
        c.close()
        try:
            from audit_log import log_action
            log_action(getattr(self.parent,"cashier_username","Unknown"),"STOCK_TRANSFER","branch_stock",no,f"{code} qty {q:g}: {fr} -> {to}",getattr(self.parent,"cashier_role",""))
        except BaseException as exc:
            _bkpos_logger.warning("Suppressed exception in multi_branch.py", exc_info=exc)
        self.refresh();self.code.delete(0,"end");self.qty.delete(0,"end");messagebox.showinfo("Transfer",f"{no} posted.",parent=self)
    def refresh(self):
        c=sqlite3.connect(DB_NAME);rows=c.execute("""SELECT transfer_no,from_branch,to_branch,barcode,description,qty,status,cashier,timestamp FROM stock_transfers ORDER BY id DESC LIMIT 300""").fetchall();c.close()
        for i in self.tree.get_children():self.tree.delete(i)
        names=dict(self.branches)
        for r in rows:self.tree.insert("", "end",values=(r[0],names.get(r[1],r[1]),names.get(r[2],r[2]),*r[3:]))
