import sqlite3
from core.config import DB_PATH
DB = DB_PATH

def db():
    return sqlite3.connect(DB)

def ensure_schema(c):
    # Keep this module self-contained and compatible with old POS databases.
    # Older builds accidentally created supplier_payments with the column
    # name 'paymen_no'. Migrate that typo before any payment/credit workflow
    # reads or writes the table.
    payment_cols = {r[1] for r in c.execute('PRAGMA table_info(supplier_payments)')}
    if payment_cols and 'payment_no' not in payment_cols and 'paymen_no' in payment_cols:
        try:
            c.execute('ALTER TABLE supplier_payments RENAME COLUMN paymen_no TO payment_no')
        except sqlite3.OperationalError:
            # Fallback for older SQLite versions: add the correct column and
            # copy the legacy values across.
            c.execute('ALTER TABLE supplier_payments ADD COLUMN payment_no TEXT')
            c.execute('UPDATE supplier_payments SET payment_no=paymen_no WHERE payment_no IS NULL')
        payment_cols = {r[1] for r in c.execute('PRAGMA table_info(supplier_payments)')}
    if payment_cols and 'payment_no' not in payment_cols:
        c.execute('ALTER TABLE supplier_payments ADD COLUMN payment_no TEXT')
    # Ensure supplier payments have the fields used by the creditor screens.
    payment_cols = {r[1] for r in c.execute('PRAGMA table_info(supplier_payments)')}
    for name, typ in [('supplier_account_no','TEXT'),('supplier_name','TEXT'),('payment_date','TEXT'),
                      ('amount','REAL'),('payment_method','TEXT'),('reference','TEXT'),
                      ('notes','TEXT'),('cashier','TEXT')]:
        if name not in payment_cols:
            c.execute(f'ALTER TABLE supplier_payments ADD COLUMN {name} {typ}')

    cols = {r[1] for r in c.execute('PRAGMA table_info(supplier_credits)')}
    if not cols:
        c.execute('''CREATE TABLE IF NOT EXISTS supplier_credits(
            id INTEGER PRIMARY KEY AUTOINCREMENT, credit_no TEXT UNIQUE NOT NULL,
            supplier_id INTEGER NOT NULL, credit_date TEXT NOT NULL,
            amount REAL NOT NULL CHECK(amount>0), reason TEXT, reference TEXT,
            created_by TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            stock_returned REAL DEFAULT 0, item_count INTEGER DEFAULT 0)''')
    else:
        for name, typ in [('stock_returned','REAL DEFAULT 0'),('item_count','INTEGER DEFAULT 0')]:
            if name not in cols:
                c.execute(f'ALTER TABLE supplier_credits ADD COLUMN {name} {typ}')
    c.execute('''CREATE TABLE IF NOT EXISTS supplier_credit_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT, credit_id INTEGER NOT NULL,
        grn_id INTEGER, grn_item_id INTEGER, barcode TEXT NOT NULL,
        description TEXT, qty REAL NOT NULL, unit_cost REAL NOT NULL,
        value REAL NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_supplier_credit_items_credit ON supplier_credit_items(credit_id)')
    c.commit()

def _has_col(c, table, col):
    return any(r[1] == col for r in c.execute(f'PRAGMA table_info({table})'))

def suppliers(c):
    if not _has_col(c, 'accounts', 'supplier_account_no'):
        return [(r[0], '', r[1]) for r in c.execute("SELECT id,name FROM accounts WHERE lower(COALESCE(type,''))='supplier' ORDER BY name COLLATE NOCASE")]
    return c.execute("SELECT id,COALESCE(supplier_account_no,''),name FROM accounts WHERE lower(COALESCE(type,''))='supplier' ORDER BY name COLLATE NOCASE").fetchall()

def purchase_rows(c, sid, acc, name):
    # GRNs are the authoritative supplier purchase documents in this POS.
    if not _has_col(c, 'grn_headers', 'supplier_account'):
        return []
    return c.execute("""SELECT id,COALESCE(grn_no,''),COALESCE(created_at,''),COALESCE(total,0)
                        FROM grn_headers
                        WHERE (supplier_account=? AND ?<>'') OR supplier_name=?
                        ORDER BY created_at,id""", (acc, acc, name)).fetchall()

def payment_rows(c, sid):
    if not _has_col(c, 'supplier_payments', 'supplier_id'):
        return []
    return c.execute("SELECT id,payment_no,payment_date,amount,payment_method,reference FROM supplier_payments WHERE supplier_id=? ORDER BY payment_date,id", (sid,)).fetchall()

def credit_rows(c, sid):
    return c.execute("SELECT id,credit_no,credit_date,amount,reason,reference FROM supplier_credits WHERE supplier_id=? ORDER BY credit_date,id", (sid,)).fetchall()

def supplier_balance(c, sid, acc, name):
    purchases = sum(float(r[3] or 0) for r in purchase_rows(c,sid,acc,name))
    payments = sum(float(r[3] or 0) for r in payment_rows(c,sid))
    credits = sum(float(r[3] or 0) for r in credit_rows(c,sid))
    return purchases, payments, credits, purchases-payments-credits

def credit_stock_available(c, sid, acc, name):
    if not _has_col(c,'grn_headers','supplier_account'):
        return []
    return c.execute('''SELECT gi.id,gh.id,gh.grn_no,gh.created_at,gi.barcode,gi.description,
                               gi.qty_received,gi.cost_price,
                               COALESCE((SELECT SUM(sci.qty) FROM supplier_credit_items sci
                                         WHERE sci.grn_item_id=gi.id),0) credited_qty
                        FROM grn_items gi JOIN grn_headers gh ON gh.id=gi.grn_id
                        WHERE ((gh.supplier_account=? AND ?<>'') OR gh.supplier_name=?)
                        ORDER BY gh.created_at DESC,gi.id''', (acc,acc,name)).fetchall()
