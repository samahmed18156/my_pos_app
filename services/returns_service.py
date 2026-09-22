"""Transactional customer return posting for BKPOS."""
from services.branch_stock_service import get_branch_soh, change_stock
from services.stock_service import record_stock_movement
from core.document_numbers import next_document_number


def post_return(conn, *, sale_id, lines, refund_type="Cash Refund", cashier="Unknown",
                branch_id=None, reason="", return_datetime=None, transaction_uid=None):
    if not lines:
        raise ValueError("A return must contain at least one item.")
    conn.execute("""CREATE TABLE IF NOT EXISTS return_history(
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        original_sale_id INTEGER NOT NULL, total_amount REAL NOT NULL DEFAULT 0,
        refund_type TEXT NOT NULL, cashier TEXT DEFAULT 'Unknown', reason TEXT DEFAULT '',
        return_no TEXT, transaction_uid TEXT)""")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(return_history)")}
    if 'return_no' not in cols: conn.execute("ALTER TABLE return_history ADD COLUMN return_no TEXT")
    if 'transaction_uid' not in cols: conn.execute("ALTER TABLE return_history ADD COLUMN transaction_uid TEXT")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_return_history_return_no ON return_history(return_no) WHERE return_no IS NOT NULL AND TRIM(return_no) <> ''")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_return_history_transaction_uid ON return_history(transaction_uid) WHERE transaction_uid IS NOT NULL AND TRIM(transaction_uid) <> ''")
    if transaction_uid:
        existing = conn.execute("SELECT id FROM return_history WHERE transaction_uid=?", (str(transaction_uid).strip(),)).fetchone()
        if existing:
            return int(existing[0]), round(float(conn.execute("SELECT total_amount FROM return_history WHERE id=?", (int(existing[0]),)).fetchone()[0] or 0), 2)
    sale = conn.execute(
        "SELECT customer_id, payment_type, COALESCE(voided,0), COALESCE(branch_id,1) "
        "FROM sales_history WHERE id=?", (int(sale_id),)
    ).fetchone()
    if not sale:
        raise ValueError("Original sale was not found.")
    customer_id, payment_type, voided, sale_branch = sale
    if voided:
        raise ValueError("Voided sales cannot receive additional returns.")
    # Returns always restore stock to the branch where the original sale was posted.
    # The caller cannot redirect stock by opening the Returns screen at another branch.
    bid = int(sale_branch or 1)
    total = 0.0
    validated = []
    for line in lines:
        item_id = int(line["sale_item_id"])
        qty = float(line["qty"])
        if qty <= 0:
            raise ValueError("Return quantity must be greater than zero.")
        row = conn.execute(
            "SELECT barcode,description,qty,price,COALESCE(cost_price,0) FROM sale_items WHERE id=? AND sale_id=?",
            (item_id, int(sale_id))
        ).fetchone()
        if not row:
            raise ValueError(f"Sale item {item_id} was not found on sale #{sale_id}.")
        code, desc, sold, price, sale_cost = row
        already = conn.execute(
            "SELECT COALESCE(SUM(qty),0) FROM return_items WHERE sale_item_id=?", (item_id,)
        ).fetchone()[0] or 0
        remaining = float(sold or 0) - float(already)
        if qty > remaining + 1e-9:
            raise ValueError(f"{desc} has only {remaining:g} remaining to return.")
        value = round(qty * float(price or 0), 2)
        total += value
        validated.append((item_id, str(code), desc or str(code), qty, float(price or 0), value, float(sale_cost or 0)))

    cur = conn.cursor()
    return_no = next_document_number(conn, "return", "CN")
    cur.execute("""INSERT INTO return_history(timestamp,original_sale_id,total_amount,refund_type,cashier,reason,return_no,transaction_uid)
                   VALUES(COALESCE(?, CURRENT_TIMESTAMP),?,?,?,?,?,?,?)""", (return_datetime, int(sale_id), round(total,2), refund_type, cashier, reason, return_no, str(transaction_uid).strip() if transaction_uid else None))
    return_id = cur.lastrowid

    # Credit-account returns post the credit in the same transaction.
    if customer_id and str(payment_type or "") == "Credit Account":
        from services.accounts_service import customer_return_credit
        customer_return_credit(conn, customer_id=int(customer_id), sale_id=int(sale_id),
                               amount=round(total,2), reference=return_no,
                               cashier=cashier, description="Customer account credit for returned goods")

    for item_id, code, desc, qty, price, value, sale_cost in validated:
        cur.execute("""INSERT INTO return_items(return_id,sale_item_id,barcode,description,qty,price,value)
                       VALUES(?,?,?,?,?,?,?)""", (return_id,item_id,code,desc,qty,price,value))
        before = get_branch_soh(conn, bid, code)
        _, after = change_stock(conn, bid, code, qty, expected_before=before)
        # A customer return re-enters inventory at the original sale COGS.
        # Recalculate the moving-average cost using the returned item's historical cost.
        current = conn.execute("SELECT COALESCE(soh,0),COALESCE(cost_price,0) FROM products WHERE barcode=?", (code,)).fetchone()
        prior_qty = max(0.0, float(current[0] or 0) - qty)
        prior_cost = float(current[1] or 0)
        total_qty = prior_qty + qty
        if total_qty > 0:
            new_cost = round(((prior_qty * prior_cost) + (qty * sale_cost)) / total_qty, 2)
            conn.execute("UPDATE products SET cost_price=? WHERE barcode=?", (new_cost, code))
        record_stock_movement(code, "RETURN", qty, reference=f"RETURN #{return_id}",
                              description=desc, qty_before=before, qty_after=after, cost_price=sale_cost,
                              reason=reason or "Customer return", cashier=cashier, conn=conn)
    if customer_id:
        sale_total = conn.execute("SELECT COALESCE(total_amount,0) FROM sales_history WHERE id=?", (int(sale_id),)).fetchone()[0] or 0
        if float(sale_total) > 0:
            from services.loyalty_service import reverse_return
            reverse_return(conn, int(customer_id), int(sale_id), return_id, total, float(sale_total))
    return return_id, round(total,2)
