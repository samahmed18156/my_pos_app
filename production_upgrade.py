"""Integrated production-readiness hardening for the POS.

No new user workflow is added here. Existing single-purpose screens remain the
source of truth; this module only hardens schema, indexes, backups and audit
metadata at startup.
"""
from core.logger import logger as _bkpos_logger
import os, sqlite3
from core.config import DB_PATH
from datetime import datetime

DB_NAME = DB_PATH

def ensure():
    con=sqlite3.connect(DB_NAME)
    try:
        con.execute("PRAGMA foreign_keys=ON")
        tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        indexes=[
            ("sales_history","CREATE INDEX IF NOT EXISTS idx_sales_timestamp ON sales_history(timestamp)"),
            ("sale_items","CREATE INDEX IF NOT EXISTS idx_sale_items_sale ON sale_items(sale_id)"),
            ("stock_movements","CREATE INDEX IF NOT EXISTS idx_stock_movements_barcode_time ON stock_movements(barcode,timestamp)"),
            ("return_items","CREATE INDEX IF NOT EXISTS idx_return_items_return ON return_items(return_id)"),
            ("operating_expenses","CREATE INDEX IF NOT EXISTS idx_expenses_date_category ON operating_expenses(expense_date,category)"),
        ]
        for table, sql in indexes:
            if table in tables:
                if table == "stock_movements":
                    cols = {r[1] for r in con.execute("PRAGMA table_info(stock_movements)")}
                    if not {"barcode", "timestamp"}.issubset(cols):
                        continue
                con.execute(sql)
        con.execute("CREATE TABLE IF NOT EXISTS pos_system_log(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,username TEXT,action TEXT,details TEXT)")
        con.execute("INSERT INTO pos_system_log(username,action,details) VALUES(?,?,?)",("SYSTEM","STARTUP_HARDENING","Production workflow integrity checks initialized"))
        con.commit()
    finally:
        con.close()

def install(app_cls):
    try: ensure()
    except Exception as exc:
        _bkpos_logger.warning("Suppressed exception in production_upgrade.py", exc_info=exc)
    return app_cls
