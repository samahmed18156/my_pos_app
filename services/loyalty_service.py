"""Auditable customer loyalty ledger for BKPOS Phase 8."""

def ensure_schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS loyalty_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER NOT NULL,
        sale_id INTEGER,
        txn_type TEXT NOT NULL,
        points INTEGER NOT NULL,
        reference TEXT NOT NULL UNIQUE,
        description TEXT DEFAULT '',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_loyalty_customer ON loyalty_transactions(customer_id)")


def balance(conn, customer_id):
    ensure_schema(conn)
    row = conn.execute("SELECT COALESCE(SUM(points),0) FROM loyalty_transactions WHERE customer_id=?", (int(customer_id),)).fetchone()
    return int(row[0] or 0)


def earn_for_sale(conn, customer_id, sale_id, amount, *, rate=10):
    if not customer_id:
        return 0
    points = int(max(0, float(amount or 0)) // float(rate))
    if points <= 0:
        return 0
    ensure_schema(conn)
    conn.execute("INSERT OR IGNORE INTO loyalty_transactions(customer_id,sale_id,txn_type,points,reference,description) VALUES(?,?,?,?,?,?)",
                 (int(customer_id), int(sale_id), 'EARN', points, f'SALE-{int(sale_id):06d}', 'Points earned from completed POS sale'))
    return points


def reverse_sale(conn, customer_id, sale_id, *, reason='Sale reversed'):
    if not customer_id:
        return 0
    ensure_schema(conn)
    row = conn.execute("SELECT COALESCE(SUM(points),0) FROM loyalty_transactions WHERE sale_id=? AND txn_type='EARN'", (int(sale_id),)).fetchone()
    earned = int(row[0] or 0)
    if earned <= 0:
        return 0
    ref = f'REVERSE-SALE-{int(sale_id):06d}'
    conn.execute("INSERT OR IGNORE INTO loyalty_transactions(customer_id,sale_id,txn_type,points,reference,description) VALUES(?,?,?,?,?,?)",
                 (int(customer_id), int(sale_id), 'REVERSAL', -earned, ref, reason))
    return earned


def reverse_return(conn, customer_id, sale_id, return_id, return_amount, sale_total):
    if not customer_id or sale_total <= 0:
        return 0
    ensure_schema(conn)
    earned = conn.execute("SELECT COALESCE(SUM(points),0) FROM loyalty_transactions WHERE sale_id=? AND txn_type='EARN'", (int(sale_id),)).fetchone()[0] or 0
    already = conn.execute("SELECT COALESCE(SUM(-points),0) FROM loyalty_transactions WHERE sale_id=? AND txn_type='RETURN_REVERSAL'", (int(sale_id),)).fetchone()[0] or 0
    target = min(int(earned), int(float(earned) * float(return_amount) / float(sale_total)))
    points = max(0, target - int(already))
    if points <= 0:
        return 0
    ref = f'RETURN-{int(return_id):06d}'
    conn.execute("INSERT OR IGNORE INTO loyalty_transactions(customer_id,sale_id,txn_type,points,reference,description) VALUES(?,?,?,?,?,?)",
                 (int(customer_id), int(sale_id), 'RETURN_REVERSAL', -points, ref, 'Points reversed for returned goods'))
    return points
