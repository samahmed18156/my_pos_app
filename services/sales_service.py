"""Transactional sales posting for BKPOS.

The UI asks for payment and customer information; this module owns the
business transaction so it can be tested without Tkinter or hardware.
"""
from services.branch_stock_service import get_branch_soh, change_stock
from services.stock_service import record_stock_movement
from core.document_numbers import next_document_number


def post_sale(conn, *, cart, total, total_cost, payment_info, payment_type,
              cashier="Unknown", branch_id=1, branch_name="Main Store",
              customer_id=None, customer_account="CASH", customer_name="Cash Sale",
              sale_datetime=None, promotion_id=None, promotion_discount=0.0, transaction_uid=None):
    if not cart:
        raise ValueError("Cannot post an empty sale.")
    conn.execute("""CREATE TABLE IF NOT EXISTS sales_history(
        id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        total_amount REAL, total_cost REAL, payment_type TEXT, cashier TEXT DEFAULT 'Unknown',
        branch_id INTEGER DEFAULT 1, branch_name TEXT DEFAULT 'Main Store', sale_no TEXT, transaction_uid TEXT)""")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(sales_history)")}
    if 'sale_no' not in cols: conn.execute("ALTER TABLE sales_history ADD COLUMN sale_no TEXT")
    if 'transaction_uid' not in cols: conn.execute("ALTER TABLE sales_history ADD COLUMN transaction_uid TEXT")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_sales_history_sale_no ON sales_history(sale_no) WHERE sale_no IS NOT NULL AND TRIM(sale_no) <> ''")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_sales_history_transaction_uid ON sales_history(transaction_uid) WHERE transaction_uid IS NOT NULL AND TRIM(transaction_uid) <> ''")
    total = round(float(total), 2)
    promotion_discount = round(float(promotion_discount or 0), 2)
    if promotion_discount < 0 or promotion_discount > total + 0.01:
        raise ValueError("Invalid promotion discount.")
    supplied_total_cost = round(float(total_cost), 2)
    if total < 0 or supplied_total_cost < 0:
        raise ValueError("Sale totals cannot be negative.")

    # The service is a business-rule boundary, so validate the cart total here
    # rather than trusting only the UI. This prevents a caller from posting a
    # sale header for one amount while recording line items for another.
    line_total = 0.0
    for item in cart:
        qty = float(item.get("qty", 0) or 0)
        price = round(float(item.get("price", 0) or 0), 2)
        if qty <= 0 or price < 0:
            raise ValueError("Sale items must have positive quantities and non-negative prices.")
        # Derive the authoritative line value from quantity × price. The UI
        # value field is presentation data and may be stale after an edit.
        line_total += round(qty * price, 2)
    line_total = round(line_total, 2)
    if abs(line_total - total) > 0.01:
        raise ValueError(f"Sale total R {total:.2f} does not match item total R {line_total:.2f}.")

    # Credit-account validation belongs here as well as in the UI. This keeps
    # direct service/API callers subject to the same debtor controls.
    if payment_type == "Credit Account":
        if not customer_id:
            raise ValueError("Credit Account sales require a customer.")
        customer_row = conn.execute(
            "SELECT name, COALESCE(credit_limit,0), COALESCE(active,1) FROM customers WHERE id=?",
            (int(customer_id),)
        ).fetchone()
        if not customer_row or not customer_row[2]:
            raise ValueError("The selected customer account is inactive or no longer exists.")
        credit_limit = float(customer_row[1] or 0)
        if credit_limit <= 0:
            raise ValueError(f"{customer_row[0]} has no credit limit.")
        current_balance = float(conn.execute(
            "SELECT COALESCE(SUM(debit-credit),0) FROM customer_account_transactions WHERE customer_id=?",
            (int(customer_id),)
        ).fetchone()[0] or 0)
        if current_balance + total > credit_limit + 0.01:
            raise ValueError(f"Credit limit exceeded for {customer_row[0]}.")

    # Inventory costing is authoritative. The UI's total_cost is treated as a
    # legacy hint only; COGS is calculated from the moving-average cost stored
    # on each product at the instant the sale is posted.
    calculated_total_cost = 0.0
    for item in cart:
        code = str(item.get("code", "")).strip()
        qty = float(item.get("qty", 0) or 0)
        if not code or qty <= 0:
            raise ValueError("Every sale item must have a product code and positive quantity.")
        row = conn.execute("SELECT COALESCE(cost_price,0),description FROM products WHERE barcode=?", (code,)).fetchone()
        if not row:
            raise ValueError(f"Product {code} no longer exists.")
        calculated_total_cost += qty * float(row[0] or 0)
    total_cost = round(calculated_total_cost, 2)

    payment_info = payment_info or {}
    cash = round(float(payment_info.get("cash", 0) or 0), 2)
    card = round(float(payment_info.get("card", 0) or 0), 2)
    tendered = round(float(payment_info.get("amount_tendered", 0) or 0), 2)
    change = round(float(payment_info.get("change", 0) or 0), 2)

    if payment_type == "Cash" and cash <= 0:
        cash = total
    if payment_type == "Card" and card <= 0:
        card = total
    if payment_type == "Credit Account":
        cash = card = 0.0
        tendered = 0.0
        change = 0.0
    if payment_type == "Split Payment":
        if cash < 0 or card < 0 or abs((cash + card) - total) > 0.01:
            raise ValueError("Split payment amounts must add up to the sale total.")
    elif payment_type not in ("Credit Account", "Discount", "Laybye", "Bank Transfer", "Other"):
        if payment_type in ("Cash", "Card") and abs((cash if payment_type == "Cash" else card) - total) > 0.01:
            raise ValueError("Payment amount does not match the sale total.")

    # Idempotency: a retried request with the same transaction UID returns the
    # original sale instead of creating a second sale/stock deduction.
    if transaction_uid:
        existing = conn.execute("SELECT id FROM sales_history WHERE transaction_uid=?", (str(transaction_uid).strip(),)).fetchone()
        if existing:
            return int(existing[0])

    # Preserve the inventory cost used for each sold line. This makes historical
    # COGS independent of later product-cost changes.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER, barcode TEXT,
            description TEXT, qty REAL, price REAL, value REAL, cost_price REAL DEFAULT 0
        )""")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(sale_items)")}
    if 'cost_price' not in cols:
        conn.execute("ALTER TABLE sale_items ADD COLUMN cost_price REAL DEFAULT 0")

    sale_no = next_document_number(conn, "sale", "INV")
    conn.execute("""
        INSERT INTO sales_history
        (timestamp,total_amount,total_cost,payment_type,cashier,customer_id,
         customer_account,customer_name,branch_id,branch_name,
         amount_tendered,change_amount,cash_amount,card_amount,sale_no,transaction_uid)
        VALUES(COALESCE(?, datetime('now','localtime')),?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (sale_datetime, total, total_cost, payment_type, cashier, customer_id,
          customer_account or "CASH", customer_name or "Cash Sale",
          int(branch_id or 1), branch_name or "Main Store", tendered, change, cash, card, sale_no,
          str(transaction_uid).strip() if transaction_uid else None))
    sale_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    if payment_type == "Credit Account":
        from customer_accounts import post_transaction, create_credit_invoice
        post_transaction(conn, int(customer_id), "INVOICE", sale_no,
                         "POS credit sale", debit=total, cashier=cashier)
        create_credit_invoice(conn, int(customer_id), sale_id, sale_no, total)

    for item in cart:
        code = str(item.get("code", ""))
        qty = float(item.get("qty", 0) or 0)
        price = round(float(item.get("price", 0) or 0), 2)
        value = round(qty * price, 2)
        if not code or qty <= 0:
            raise ValueError("Every sale item must have a product code and positive quantity.")
        row = conn.execute("SELECT COALESCE(cost_price,0),description FROM products WHERE barcode=?", (code,)).fetchone()
        if not row:
            raise ValueError(f"Product {code} no longer exists.")
        before = get_branch_soh(conn, branch_id, code)
        if before + 1e-9 < qty:
            raise ValueError(f"Insufficient stock for {row[1] or code}. Available: {before:g}, requested: {qty:g}.")
        _, after = change_stock(conn, branch_id, code, -qty, expected_before=before)
        record_stock_movement(code, "SALE", -qty, reference=f"SALE #{sale_id}",
                              description=item.get("name", row[1] or code),
                              qty_before=before, qty_after=after,
                              cost_price=float(row[0] or 0), reason="Normal sale",
                              cashier=cashier, conn=conn)
        unit_cost = float(row[0] or 0)
        conn.execute("""INSERT INTO sale_items(sale_id,barcode,description,qty,price,value,cost_price)
                        VALUES(?,?,?,?,?,?,?)""", (sale_id, code, item.get("name", row[1] or code), qty, price, value, unit_cost))

    if promotion_id and promotion_discount > 0:
        from services.promotion_service import record_redemption
        record_redemption(conn, promotion_id, sale_id, promotion_discount)
    if customer_id:
        from services.loyalty_service import earn_for_sale
        earn_for_sale(conn, int(customer_id), sale_id, total)
    return sale_id
