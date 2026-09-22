"""Document-history viewer bridge for BKPOS account ledgers."""
from __future__ import annotations
from core.logger import logger as _bkpos_logger
import sqlite3
from datetime import datetime
from jasper_reports.jasper_receipt import write_jrpxml, open_in_jasperviewer
from core.config import DB_PATH


def _conn(conn=None):
    return conn or sqlite3.connect(DB_PATH)


def _branch(conn, branch_id):
    try:
        row = conn.execute("SELECT name,COALESCE(address,''),COALESCE(phone,'') FROM branches WHERE id=?", (branch_id,)).fetchone()
        if row: return row
    except Exception as exc:
        _bkpos_logger.warning("Suppressed exception in document_viewer.py", exc_info=exc)
    return ("FAMILY SUPERMARKET", "", "")


def _open(kind, doc_id, conn=None, parent=None):
    own = conn is None
    c = _conn(conn)
    try:
        if kind == "SALE":
            h = c.execute("SELECT id,timestamp,total_amount,payment_type,cashier,customer_name,branch_id,branch_name FROM sales_history WHERE id=?", (int(doc_id),)).fetchone()
            if not h: raise ValueError("Sale invoice could not be found.")
            items = c.execute("SELECT barcode,description,qty,price,value FROM sale_items WHERE sale_id=? ORDER BY id", (h[0],)).fetchall()
            branch = _branch(c, h[6])
            path = write_jrpxml(items=[{"code":r[0],"name":r[1],"qty":r[2],"price":r[3],"value":r[4]} for r in items], total=h[2], payment_type=h[3] or "Credit Account", cashier=h[4] or "", invoice_number=f"INV-{h[0]:06d}", customer_name=h[5] or "Cash Sale", store_name=branch[0] or h[7] or "FAMILY SUPERMARKET", store_address=branch[1], store_phone=branch[2], sale_datetime=datetime.fromisoformat(str(h[1]).replace(' ','T')) if h[1] else None)
        elif kind == "GRN":
            h = c.execute("SELECT id,grn_no,supplier_name,supplier_invoice,reference,subtotal,vat,total,created_at,cashier,supplier_id FROM grn_headers WHERE id=?", (int(doc_id),)).fetchone()
            if not h: raise ValueError("GRN could not be found.")
            items = c.execute("SELECT barcode,description,qty_received,cost_price,value FROM grn_items WHERE grn_id=? ORDER BY id", (h[0],)).fetchall()
            path = write_jrpxml(items=[{"code":r[0],"name":r[1],"qty":r[2],"price":r[3],"value":r[4]} for r in items], total=h[7], payment_type="SUPPLIER PURCHASE", cashier=h[9] or "", invoice_number=h[1], customer_name=h[2] or "", store_name="GOODS RECEIVED NOTE", store_address=f"Supplier Invoice: {h[3] or '-'}  Reference: {h[4] or '-'}", store_phone="", sale_datetime=datetime.fromisoformat(str(h[8]).replace(' ','T')) if h[8] else None)
        else:
            raise ValueError(f"Unsupported document type: {kind}")
        ok, msg = open_in_jasperviewer(path)
        if not ok: raise RuntimeError(msg)
        return path
    finally:
        if own: c.close()
