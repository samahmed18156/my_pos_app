"""Transactional GRN posting for BKPOS.

A GRN is the authoritative supplier purchase document. Posting one atomically:
- creates the GRN header/items
- receives stock into the selected branch
- updates the global product stock
- records stock movements
- creates one supplier PURCHASE ledger entry
"""
from datetime import datetime
from services.branch_stock_service import get_branch_soh, change_stock
from services.stock_service import record_stock_movement
from core.document_numbers import next_document_number


def _money(v):
    return round(float(v or 0), 2)


def ensure_schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS grn_headers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        grn_no TEXT UNIQUE NOT NULL,
        supplier_id INTEGER,
        supplier_account TEXT,
        supplier_name TEXT NOT NULL,
        supplier_invoice TEXT,
        reference TEXT,
        vat_mode TEXT,
        subtotal REAL NOT NULL DEFAULT 0,
        vat REAL NOT NULL DEFAULT 0,
        total REAL NOT NULL DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        cashier TEXT DEFAULT 'Unknown')""")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(grn_headers)")}
    if 'transaction_uid' not in cols:
        conn.execute("ALTER TABLE grn_headers ADD COLUMN transaction_uid TEXT")
    if 'supplier_id' not in cols:
        conn.execute("ALTER TABLE grn_headers ADD COLUMN supplier_id INTEGER")
    if 'paid' not in cols:
        conn.execute("ALTER TABLE grn_headers ADD COLUMN paid REAL NOT NULL DEFAULT 0")
    if 'outstanding' not in cols:
        conn.execute("ALTER TABLE grn_headers ADD COLUMN outstanding REAL NOT NULL DEFAULT 0")
    if 'status' not in cols:
        conn.execute("ALTER TABLE grn_headers ADD COLUMN status TEXT NOT NULL DEFAULT 'UNPAID'")
    if 'po_no' not in cols:
        conn.execute("ALTER TABLE grn_headers ADD COLUMN po_no TEXT")
    conn.execute("""CREATE TABLE IF NOT EXISTS grn_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        grn_id INTEGER NOT NULL,
        barcode TEXT NOT NULL,
        description TEXT,
        soh_before REAL DEFAULT 0,
        order_qty REAL DEFAULT 0,
        qty_received REAL NOT NULL,
        cost_price REAL NOT NULL,
        value REAL NOT NULL)""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_grn_headers_supplier_id ON grn_headers(supplier_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_grn_items_grn_id ON grn_items(grn_id)")


def post_grn(conn, *, supplier_id, supplier_account, supplier_name, items,
             branch_id=1, cashier='Unknown', supplier_invoice='', reference='',
             vat_mode='Inclusive', grn_no=None, received_date=None, transaction_uid=None, po_no=None):
    ensure_schema(conn)
    if transaction_uid:
        existing = conn.execute("SELECT id,grn_no,total FROM grn_headers WHERE transaction_uid=?", (str(transaction_uid).strip(),)).fetchone()
        if existing:
            return {'grn_id': int(existing[0]), 'grn_no': existing[1], 'total': float(existing[2] or 0), 'duplicate': True}
    if not supplier_id:
        raise ValueError("A supplier account is required.")
    if not supplier_name:
        raise ValueError("Supplier name is required.")
    if not items:
        raise ValueError("A GRN must contain at least one item.")
    bid = int(branch_id or 1)
    prepared = []
    subtotal = 0.0
    for item in items:
        code = str(item.get('barcode') or item.get('code') or '').strip()
        qty = float(item.get('qty', item.get('quantity', 0)) or 0)
        cost = _money(item.get('cost', item.get('cost_price', 0)))
        if not code or qty <= 0 or cost < 0:
            raise ValueError("Each GRN item needs a product, positive quantity and non-negative cost.")
        row = conn.execute("SELECT description FROM products WHERE barcode=?", (code,)).fetchone()
        if not row:
            raise ValueError(f"Product {code} was not found in Product Master.")
        before = get_branch_soh(conn, bid, code)
        value = _money(qty * cost)
        subtotal += value
        prepared.append((code, item.get('description') or row[0] or code, qty, cost, before, value))
    subtotal = _money(subtotal)
    if str(vat_mode).lower() == 'inclusive':
        vat = _money(subtotal * 15 / 115)
        net = _money(subtotal - vat)
        total = subtotal
    else:
        vat = _money(subtotal * 0.15)
        net = subtotal
        total = _money(subtotal + vat)
    if not grn_no:
        grn_no = next_document_number(conn, "grn", "GRN")
    stamp = received_date or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cur = conn.execute("""INSERT INTO grn_headers
        (grn_no,supplier_id,supplier_account,supplier_name,supplier_invoice,reference,
         vat_mode,subtotal,vat,total,created_at,cashier,paid,outstanding,status,transaction_uid,po_no)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (grn_no, int(supplier_id), supplier_account or '', supplier_name,
         supplier_invoice or '', reference or '', vat_mode or 'Inclusive',
         net, vat, total, stamp, cashier or 'Unknown', 0.0, total, 'UNPAID', str(transaction_uid).strip() if transaction_uid else None, po_no or None))
    gid = cur.lastrowid
    for code, desc, qty, cost, before, value in prepared:
        _, after = change_stock(conn, bid, code, qty, expected_before=before)
        # BKPOS uses perpetual weighted-average inventory costing.  The product
        # master cost is the current moving-average cost, not simply the last
        # supplier invoice cost. Existing stock and its current cost form the
        # opening layer for the calculation.
        current = conn.execute("SELECT COALESCE(soh,0), COALESCE(cost_price,0) FROM products WHERE barcode=?", (code,)).fetchone()
        old_qty = max(0.0, float(current[0] or 0) - qty)
        old_cost = float(current[1] or 0)
        new_qty = old_qty + qty
        weighted_cost = cost if new_qty <= 0 else _money(((old_qty * old_cost) + (qty * cost)) / new_qty)
        conn.execute("UPDATE products SET cost_price=? WHERE barcode=?", (weighted_cost, code))
        conn.execute("""INSERT INTO grn_items
            (grn_id,barcode,description,soh_before,order_qty,qty_received,cost_price,value)
            VALUES(?,?,?,?,?,?,?,?)""", (gid, code, desc, before, 0, qty, cost, value))
        record_stock_movement(code, 'GRN', qty, reference=grn_no, description=desc,
                              qty_before=before, qty_after=after, cost_price=cost,
                              reason='Goods received', cashier=cashier, conn=conn)
    # Keep the legacy supplier transaction ledger synchronized, but only once per GRN.
    conn.execute("""INSERT INTO account_transactions(account_id,txn_type,total_amount,txn_date)
        VALUES(?,?,?,?)""", (int(supplier_id), 'PURCHASE', total, stamp))
    if po_no:
        from services.purchase_order_service import update_receipts_for_po
        update_receipts_for_po(conn, po_no)
    return {'grn_id': gid, 'grn_no': grn_no, 'subtotal': net, 'vat': vat, 'total': total,
            'item_count': len(prepared), 'branch_id': bid, 'po_no': po_no or ''}
