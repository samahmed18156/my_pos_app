"""Transactional supplier stock-return / credit-note posting for BKPOS."""
from datetime import datetime
from services.branch_stock_service import get_branch_soh, change_stock
from services.stock_service import record_stock_movement
from core.document_numbers import next_document_number


def _money(v): return round(float(v or 0), 2)


def ensure_schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS supplier_credits(
        id INTEGER PRIMARY KEY AUTOINCREMENT, credit_no TEXT UNIQUE NOT NULL,
        supplier_id INTEGER NOT NULL, credit_date TEXT NOT NULL,
        amount REAL NOT NULL CHECK(amount>0), reason TEXT, reference TEXT,
        created_by TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        stock_returned REAL DEFAULT 0, item_count INTEGER DEFAULT 0)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS supplier_credit_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT, credit_id INTEGER NOT NULL,
        grn_id INTEGER, grn_item_id INTEGER, barcode TEXT NOT NULL,
        description TEXT, qty REAL NOT NULL, unit_cost REAL NOT NULL,
        value REAL NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(supplier_credits)")}
    if "transaction_uid" not in cols:
        conn.execute("ALTER TABLE supplier_credits ADD COLUMN transaction_uid TEXT")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_supplier_credits_transaction_uid ON supplier_credits(transaction_uid) WHERE transaction_uid IS NOT NULL AND TRIM(transaction_uid) <> ''")


def post_supplier_stock_credit(conn, *, supplier_id, items, branch_id=1,
                               credit_no=None, credit_date=None, reason='Stock returned to supplier',
                               reference='', created_by='Unknown', transaction_uid=None):
    ensure_schema(conn)
    if transaction_uid:
        existing = conn.execute("SELECT id,credit_no,amount FROM supplier_credits WHERE transaction_uid=?", (str(transaction_uid).strip(),)).fetchone()
        if existing:
            return {'credit_id': int(existing[0]), 'credit_no': existing[1], 'amount': float(existing[2] or 0), 'duplicate': True}
    if not supplier_id: raise ValueError('A supplier account is required.')
    if not items: raise ValueError('A supplier credit must contain at least one item.')
    bid = int(branch_id or 1)
    prepared=[]; total=0.0; total_qty=0.0
    for item in items:
        gi=int(item.get('grn_item_id'))
        qty=float(item.get('qty',0) or 0)
        if qty<=0: raise ValueError('Supplier credit quantities must be greater than zero.')
        row=conn.execute('''SELECT gi.grn_id,gi.barcode,gi.description,gi.qty_received,gi.cost_price,
                                   gh.supplier_id,COALESCE((SELECT SUM(sci.qty) FROM supplier_credit_items sci WHERE sci.grn_item_id=gi.id),0)
                            FROM grn_items gi JOIN grn_headers gh ON gh.id=gi.grn_id WHERE gi.id=?''',(gi,)).fetchone()
        if not row: raise ValueError(f'GRN item {gi} was not found.')
        grn_id,code,desc,received,cost,grn_supplier,already=row
        if int(grn_supplier or 0) != int(supplier_id): raise ValueError('GRN item belongs to a different supplier.')
        available=float(received or 0)-float(already or 0)
        if qty>available+1e-9: raise ValueError(f'{desc or code} has only {available:g} available for supplier credit.')
        before=get_branch_soh(conn,bid,code)
        if before+1e-9<qty: raise ValueError(f'Insufficient branch stock for {desc or code}. Available: {before:g}, requested: {qty:g}.')
        value=_money(qty*float(cost or 0)); total+=value; total_qty+=qty
        prepared.append((gi,grn_id,code,desc or code,qty,float(cost or 0),value,before))
    total=_money(total)
    if total<=0: raise ValueError('Supplier credit value must be greater than zero.')
    # Do not let a stock credit silently create an unexplained negative creditor balance.
    purchase=float(conn.execute("SELECT COALESCE(SUM(total_amount),0) FROM account_transactions WHERE account_id=? AND txn_type='PURCHASE'",(int(supplier_id),)).fetchone()[0] or 0)
    payments=float(conn.execute("SELECT COALESCE(SUM(total_amount),0) FROM account_transactions WHERE account_id=? AND txn_type='PAYMENT'",(int(supplier_id),)).fetchone()[0] or 0)
    credits=float(conn.execute("SELECT COALESCE(SUM(amount),0) FROM supplier_credits WHERE supplier_id=?",(int(supplier_id),)).fetchone()[0] or 0)
    if total > purchase-payments-credits+0.01:
        raise ValueError('Supplier credit exceeds the current supplier outstanding balance.')
    if not credit_no:
        credit_no=next_document_number(conn, 'supplier_credit', 'SCN')
    cur=conn.execute('''INSERT INTO supplier_credits(credit_no,supplier_id,credit_date,amount,reason,reference,created_by,stock_returned,item_count,transaction_uid)
                        VALUES(?,?,?,?,?,?,?,?,?,?)''',(credit_no,int(supplier_id),credit_date or datetime.now().strftime('%Y-%m-%d'),total,reason or '',reference or '',created_by or 'Unknown',total_qty,len(prepared),str(transaction_uid).strip() if transaction_uid else None))
    cid=cur.lastrowid
    for gi,grn_id,code,desc,qty,cost,value,before in prepared:
        _,after=change_stock(conn,bid,code,-qty,expected_before=before)
        conn.execute('''INSERT INTO supplier_credit_items(credit_id,grn_id,grn_item_id,barcode,description,qty,unit_cost,value)
                        VALUES(?,?,?,?,?,?,?,?)''',(cid,grn_id,gi,code,desc,qty,cost,value))
        # Reduce the originating GRN's outstanding liability as well as the
        # supplier control balance. Never let invoice outstanding go negative.
        cols = {r[1] for r in conn.execute("PRAGMA table_info(grn_headers)")}
        if {'paid','outstanding','status'}.issubset(cols):
            current = conn.execute("SELECT total,paid,outstanding FROM grn_headers WHERE id=?", (grn_id,)).fetchone()
            if current:
                total_now, paid_now, out_now = (_money(current[0]), _money(current[1]), _money(current[2]))
                reduce_out = min(value, out_now)
                new_out = max(0.0, out_now - reduce_out)
                new_total = total_now
                # If the GRN was already paid, the credit becomes an unapplied
                # supplier credit rather than creating a negative invoice.
                status = 'PAID' if new_out <= 0.005 else ('PART PAID' if paid_now > 0.005 else 'UNPAID')
                conn.execute("UPDATE grn_headers SET total=?,outstanding=?,status=? WHERE id=?",
                             (new_total,new_out,status,grn_id))
        record_stock_movement(code,'SUPPLIER RETURN',-qty,reference=credit_no,description=desc,
                              qty_before=before,qty_after=after,cost_price=cost,reason=reason,cashier=created_by,conn=conn)
    return {'credit_id':cid,'credit_no':credit_no,'amount':total,'stock_returned':total_qty,'item_count':len(prepared),'branch_id':bid}
