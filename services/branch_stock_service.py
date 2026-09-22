"""Branch-aware stock operations for BKPOS.

Rules:
- branch_stock is authoritative for stock by branch.
- products.soh remains the global total across all branches for legacy screens/reports.
- Every branch stock change and global total change occurs in the same transaction.
"""
import sqlite3
from core.config import DB_PATH
from core.document_numbers import next_document_number

DB_NAME = DB_PATH


def ensure_schema(conn=None):
    own = conn is None
    c = conn or sqlite3.connect(DB_NAME)
    cur = c.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS branch_stock(
        branch_id INTEGER NOT NULL,
        barcode TEXT NOT NULL,
        soh REAL NOT NULL DEFAULT 0,
        PRIMARY KEY(branch_id, barcode))""")
    cur.execute("""CREATE TABLE IF NOT EXISTS stock_transfers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transfer_no TEXT NOT NULL,
        from_branch INTEGER NOT NULL,
        to_branch INTEGER NOT NULL,
        barcode TEXT NOT NULL,
        description TEXT,
        qty REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'POSTED',
        cashier TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)""")
    # Seed missing rows. Existing products.soh is treated as Main Store stock
    # only when no branch rows exist yet; this preserves existing installations.
    branches = cur.execute("SELECT id FROM branches ORDER BY id").fetchall()
    products = cur.execute("SELECT barcode, COALESCE(soh,0) FROM products").fetchall()
    for (bid,) in branches:
        for code, total_soh in products:
            exists = cur.execute("SELECT 1 FROM branch_stock WHERE branch_id=? AND barcode=?", (bid, code)).fetchone()
            if exists is None:
                seed = total_soh if bid == 1 else 0
                cur.execute("INSERT INTO branch_stock(branch_id,barcode,soh) VALUES(?,?,?)", (bid, code, seed))
    if own:
        c.commit(); c.close()
    return c


def _branch_id(branch_id):
    try:
        bid = int(branch_id)
    except Exception:
        bid = 1
    return bid if bid > 0 else 1


def get_branch_soh(conn, branch_id, barcode):
    ensure_schema(conn)
    row = conn.execute("SELECT COALESCE(soh,0) FROM branch_stock WHERE branch_id=? AND barcode=?", (_branch_id(branch_id), str(barcode))).fetchone()
    return float(row[0]) if row else 0.0


def change_stock(conn, branch_id, barcode, delta, *, expected_before=None):
    """Atomically change one branch's stock and the global product total."""
    ensure_schema(conn)
    bid = _branch_id(branch_id)
    code = str(barcode)
    delta = float(delta)
    if delta == 0:
        return get_branch_soh(conn, bid, code), get_branch_soh(conn, bid, code)
    product = conn.execute("SELECT COALESCE(soh,0) FROM products WHERE barcode=?", (code,)).fetchone()
    if product is None:
        raise ValueError(f"Product {code} was not found in Product Master.")
    row = conn.execute("SELECT COALESCE(soh,0) FROM branch_stock WHERE branch_id=? AND barcode=?", (bid, code)).fetchone()
    if row is None:
        conn.execute("INSERT INTO branch_stock(branch_id,barcode,soh) VALUES(?,?,0)", (bid, code))
        before = 0.0
    else:
        before = float(row[0] or 0)
    if expected_before is not None and abs(before - float(expected_before)) > 1e-9:
        raise ValueError(f"Stock changed while processing {code}. Please retry.")
    after = before + delta
    if after < -1e-9:
        raise ValueError(f"Insufficient stock for {code}. Available: {before:g}, requested: {-delta:g}.")
    conn.execute("UPDATE branch_stock SET soh=? WHERE branch_id=? AND barcode=?", (after, bid, code))
    # products.soh is the global total. Adjust it by exactly the same delta.
    conn.execute("UPDATE products SET soh=COALESCE(soh,0)+? WHERE barcode=?", (delta, code))
    return before, after


def transfer(conn, from_branch, to_branch, barcode, qty, cashier="Unknown"):
    ensure_schema(conn)
    fr, to = _branch_id(from_branch), _branch_id(to_branch)
    code = str(barcode)
    qty = float(qty)
    if fr == to:
        raise ValueError("From and To branches must be different.")
    if qty <= 0:
        raise ValueError("Transfer quantity must be greater than zero.")
    row = conn.execute("SELECT description FROM products WHERE barcode=?", (code,)).fetchone()
    if not row:
        raise ValueError(f"Product {code} was not found in Product Master.")
    before, after = change_stock(conn, fr, code, -qty)
    try:
        change_stock(conn, to, code, qty)
        no = next_document_number(conn, "transfer", "TRF")
        conn.execute("INSERT INTO stock_transfers(transfer_no,from_branch,to_branch,barcode,description,qty,cashier) VALUES(?,?,?,?,?,?,?)",
                     (no, fr, to, code, row[0], qty, cashier))
        return no, before, after
    except Exception:
        raise
