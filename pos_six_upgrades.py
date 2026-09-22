from core.logger import logger as _bkpos_logger

import sqlite3, tkinter as tk
from tkinter import messagebox
from core.config import DB_PATH
DB_NAME=DB_PATH

def ensure_schema():
    c=sqlite3.connect(DB_NAME);cur=c.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS audit_log(
      id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
      username TEXT,role TEXT,action TEXT,entity_type TEXT,entity_id TEXT,details TEXT,branch_id INTEGER DEFAULT 1)""")
    # Some test/development databases do not create GRN tables until the GRN
    # window is opened. The audit trigger requires the table to exist at trigger
    # creation time, so provide a harmless compatibility shell here.
    cur.execute("""CREATE TABLE IF NOT EXISTS grn_headers(
      id INTEGER PRIMARY KEY AUTOINCREMENT, grn_no TEXT, total REAL DEFAULT 0)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS audit_context(
      id INTEGER PRIMARY KEY CHECK(id=1),username TEXT,role TEXT,branch_id INTEGER DEFAULT 1)""")
    cur.execute("INSERT OR IGNORE INTO audit_context(id,username,role,branch_id) VALUES(1,'SYSTEM','SYSTEM',1)")
    # Database-level audit triggers cover changes made by the existing POS windows.
    # Recreate them so older installations are upgraded from the pre-canonical
    # audit INSERT shape to the current schema without touching audit history.
    for _trigger in (
        "trg_audit_price_change", "trg_audit_stock_change", "trg_audit_sale",
        "trg_audit_return", "trg_audit_grn",
    ):
        cur.execute(f"DROP TRIGGER IF EXISTS {_trigger}")
    cur.execute("""CREATE TRIGGER IF NOT EXISTS trg_audit_price_change AFTER UPDATE OF selling_price ON products
      WHEN OLD.selling_price IS NOT NEW.selling_price BEGIN
      INSERT INTO audit_log(event_time,username,role,action,entity_type,entity_id,details,branch_id,event_type)
      SELECT datetime('now','localtime'),username,role,'PRICE_CHANGED','product',NEW.barcode,
             'Selling price: R '||printf('%.2f',OLD.selling_price)||' -> R '||printf('%.2f',NEW.selling_price),branch_id,'PRICE_CHANGED' 
      FROM audit_context WHERE id=1; END""")
    cur.execute("""CREATE TRIGGER IF NOT EXISTS trg_audit_stock_change AFTER UPDATE OF soh ON products
      WHEN OLD.soh IS NOT NEW.soh BEGIN
      INSERT INTO audit_log(event_time,username,role,action,entity_type,entity_id,details,branch_id,event_type)
      SELECT datetime('now','localtime'),username,role,'STOCK_CHANGED','product',NEW.barcode,
             'SOH: '||printf('%g',OLD.soh)||' -> '||printf('%g',NEW.soh),branch_id,'STOCK_CHANGED' 
      FROM audit_context WHERE id=1; END""")
    cur.execute("""CREATE TRIGGER IF NOT EXISTS trg_audit_sale AFTER INSERT ON sales_history BEGIN
      INSERT INTO audit_log(event_time,username,role,action,entity_type,entity_id,details,branch_id,event_type)
      SELECT datetime('now','localtime'),username,role,'SALE_CREATED','sale',NEW.id,
             'Total: R '||printf('%.2f',COALESCE(NEW.total_amount,0))||' | Payment: '||COALESCE(NEW.payment_type,''),branch_id,'SALE_CREATED' 
      FROM audit_context WHERE id=1; END""")
    cur.execute("""CREATE TRIGGER IF NOT EXISTS trg_audit_return AFTER INSERT ON return_history BEGIN
      INSERT INTO audit_log(event_time,username,role,action,entity_type,entity_id,details,branch_id,event_type)
      SELECT datetime('now','localtime'),username,role,'RETURN_REFUND','return',NEW.id,
             'Original sale: '||NEW.original_sale_id||' | Total: R '||printf('%.2f',NEW.total_amount)||' | '||NEW.refund_type,branch_id,'RETURN_REFUND' 
      FROM audit_context WHERE id=1; END""")
    cur.execute("""CREATE TRIGGER IF NOT EXISTS trg_audit_grn AFTER INSERT ON grn_headers BEGIN
      INSERT INTO audit_log(event_time,username,role,action,entity_type,entity_id,details,branch_id,event_type)
      SELECT datetime('now','localtime'),username,role,'GRN_POSTED','grn',NEW.id,
             NEW.grn_no||' | Total: R '||printf('%.2f',NEW.total),branch_id,'GRN_POSTED' 
      FROM audit_context WHERE id=1; END""")
    cur.execute("""CREATE TABLE IF NOT EXISTS customers(
      id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,phone TEXT,address TEXT,email TEXT,
      credit_limit REAL DEFAULT 0,active INTEGER DEFAULT 1,created_at DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS branch_stock(
      branch_id INTEGER,barcode TEXT,soh REAL DEFAULT 0,PRIMARY KEY(branch_id,barcode))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS stock_transfers(
      id INTEGER PRIMARY KEY AUTOINCREMENT,transfer_no TEXT,from_branch INTEGER,to_branch INTEGER,
      barcode TEXT,description TEXT,qty REAL,status TEXT DEFAULT 'POSTED',cashier TEXT,timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    # Backward-compatible indexes improve report performance.
    for sql in ["CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_log(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_sales_time ON sales_history(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_sale_items_barcode ON sale_items(barcode)",
                "CREATE INDEX IF NOT EXISTS idx_returns_time ON return_history(timestamp)"]:
        try:cur.execute(sql)
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in pos_six_upgrades.py", exc_info=exc)
    branches=cur.execute("SELECT id FROM branches").fetchall()
    products=cur.execute("SELECT barcode,soh FROM products").fetchall()
    for (bid,) in branches:
        for code,soh in products:
            cur.execute("INSERT OR IGNORE INTO branch_stock(branch_id,barcode,soh) VALUES(?,?,?)",(bid,code,soh if bid==1 else 0))
    c.commit();c.close()

def audit(user,action,entity="",eid="",details="",role="",branch=1):
    try:
        c=sqlite3.connect(DB_NAME);c.execute("INSERT INTO audit_log(event_time,username,role,action,entity_type,entity_id,details,branch_id,event_type) VALUES(datetime('now','localtime'),?,?,?,?,?,?,?,?)",
          (user or "Unknown",role or "",action,entity,str(eid or ""),details,branch or 1,action));c.commit();c.close()
    except Exception as exc:
        _bkpos_logger.warning("Suppressed exception in pos_six_upgrades.py", exc_info=exc)

def install(app_cls):
    ensure_schema()
    # Import windows only after the POS/database are ready.
    from audit_log import AuditLogWindow
    from advanced_reports import AdvancedReportsWindow
    from barcode_labels import BarcodeLabelWindow
    from customers import CustomerManagerWindow
    from multi_branch import BranchTransferWindow, ensure_schema as branch_schema
    from disaster_recovery import DisasterRecoveryWindow
    branch_schema()

    # Establish the cashier's assigned branch without changing login.py.
    original_init=app_cls.__init__
    def init_with_branch(self,*args,**kwargs):
        original_init(self,*args,**kwargs)
        try:
            c=sqlite3.connect(DB_NAME)
            row=c.execute("SELECT branch_id FROM users WHERE username=?",(getattr(self,"cashier_username",""),)).fetchone()
            c.close()
            self.current_branch_id=int(row[0] or 1) if row else 1
        except Exception:self.current_branch_id=1
        try:
            c=sqlite3.connect(DB_NAME);row=c.execute("SELECT name FROM branches WHERE id=?",(self.current_branch_id,)).fetchone();c.close()
            self.current_branch_name=row[0] if row else "Main Store"
        except Exception:self.current_branch_name="Main Store"
        try:
            c=sqlite3.connect(DB_NAME)
            c.execute("UPDATE audit_context SET username=?,role=?,branch_id=? WHERE id=1",
                      (getattr(self,"cashier_username","Unknown"),getattr(self,"cashier_role",""),getattr(self,"current_branch_id",1)))
            c.commit();c.close()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in pos_six_upgrades.py", exc_info=exc)
        audit(getattr(self,"cashier_username","Unknown"),"LOGIN","user",getattr(self,"cashier_username",""),"POS session started",getattr(self,"cashier_role",""),getattr(self,"current_branch_id",1))
    app_cls.__init__=init_with_branch

    # Keep the completed sale tied to the cashier's assigned branch.
    original_checkout=app_cls.checkout
    def checkout_with_branch(self,event=None):
        before=sqlite3.connect(DB_NAME).execute("SELECT COALESCE(MAX(id),0) FROM sales_history").fetchone()[0]
        result=original_checkout(self,event)
        try:
            c=sqlite3.connect(DB_NAME)
            row=c.execute("SELECT id FROM sales_history ORDER BY id DESC LIMIT 1").fetchone()
            if row and row[0]>before:
                c.execute("UPDATE sales_history SET branch_id=?,branch_name=? WHERE id=?",
                          (getattr(self,"current_branch_id",1),getattr(self,"current_branch_name","Main Store"),row[0]))
                c.commit()
            c.close()
        except Exception as exc:
            _bkpos_logger.warning("Suppressed exception in pos_six_upgrades.py", exc_info=exc)
        return result
    app_cls.checkout=checkout_with_branch

    # Logout audit.
    original_logout=getattr(app_cls,"log_out",None)
    if original_logout:
        def logout_audited(self,*args,**kwargs):
            audit(getattr(self,"cashier_username","Unknown"),"LOGOUT","user",getattr(self,"cashier_username",""),"POS session ended",getattr(self,"cashier_role",""),getattr(self,"current_branch_id",1))
            return original_logout(self,*args,**kwargs)
        app_cls.log_out=logout_audited

    # Add a dedicated menu while preserving all existing menus and permissions.
    original_menu=app_cls.create_menu_bar
    def menu_with_six(self):
        original_menu(self)
        mb=self.nametowidget(self.cget("menu"))
        mg=tk.Menu(mb,tearoff=0)
        mg.add_command(label="🔐 Audit Log",command=lambda:AuditLogWindow(self))
        if getattr(self,"is_admin",False) or self.can("can_view_reports"):
            mg.add_command(label="📈 Advanced Reports",command=lambda:AdvancedReportsWindow(self))
        if getattr(self,"is_admin",False) or self.can("can_access_stock"):
            mg.add_separator()
            mg.add_command(label="🏷 Barcode & Label Printing",command=lambda:BarcodeLabelWindow(self))
            mg.add_command(label="🔄 Branch Stock Transfers",command=lambda:BranchTransferWindow(self))
        mg.add_command(label="👥 Customer Management",command=lambda:CustomerManagerWindow(self))
        if getattr(self,"is_admin",False):
            mg.add_separator()
            mg.add_command(label="🛡 Disaster Recovery Center",command=lambda:DisasterRecoveryWindow(self))
        mb.add_cascade(label="Upgrades",menu=mg)
    app_cls.create_menu_bar=menu_with_six

    # Audit return/refund operations without changing returns.py.
    try:
        from returns import ReturnsWindow
        old_return=ReturnsWindow.process_return
        def audited_return(self,*args,**kwargs):
            result=old_return(self,*args,**kwargs)
            try:
                audit(getattr(self.parent,"cashier_username","Unknown"),"RETURN_REFUND","return",
                      getattr(self,"return_id",""),"Return/refund processed",getattr(self.parent,"cashier_role",""),
                      getattr(self.parent,"current_branch_id",1))
            except Exception as exc:
                _bkpos_logger.warning("Suppressed exception in pos_six_upgrades.py", exc_info=exc)
            return result
        ReturnsWindow.process_return=audited_return
    except Exception as exc:
        _bkpos_logger.warning("Suppressed exception in pos_six_upgrades.py", exc_info=exc)

    return app_cls
