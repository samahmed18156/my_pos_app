"""Transactional debtor/creditor operations for BKPOS.

These functions contain no Tkinter code.  They are deliberately small and
strict so the same accounting rules can be tested and later reused by the UI.
"""
from datetime import datetime


def _money(value):
    return round(float(value or 0), 2)


def customer_payment(conn, *, customer_id, amount, payment_method="Cash",
                     reference="", notes="", cashier="Unknown"):
    """Receive a customer payment and allocate it oldest invoice first."""
    customer_id = int(customer_id)
    amount = _money(amount)
    if amount <= 0:
        raise ValueError("Customer payment must be greater than zero.")
    bal = _money(conn.execute(
        "SELECT COALESCE(SUM(debit-credit),0) FROM customer_account_transactions WHERE customer_id=?",
        (customer_id,)).fetchone()[0])
    if amount > bal + 0.01:
        raise ValueError(f"Payment exceeds outstanding balance of R {bal:,.2f}.")

    cur = conn.execute("""INSERT INTO customer_account_payments
        (customer_id,amount,payment_method,reference,notes,cashier)
        VALUES(?,?,?,?,?,?)""",
        (customer_id, amount, payment_method or "Cash", reference or "",
         notes or "", cashier or "Unknown"))
    payment_id = cur.lastrowid
    remaining = amount
    invoices = conn.execute("""SELECT id,total,paid,outstanding FROM customer_account_invoices
        WHERE customer_id=? AND outstanding>0.005
        ORDER BY invoice_date,id""", (customer_id,)).fetchall()
    for invoice_id, total, paid, outstanding in invoices:
        if remaining <= 0.005:
            break
        applied = min(remaining, _money(outstanding))
        new_paid = _money(paid) + applied
        new_outstanding = max(0.0, _money(total) - new_paid)
        status = "PAID" if new_outstanding <= 0.005 else "PART PAID"
        conn.execute("""INSERT INTO customer_account_payment_allocations
            (payment_id,invoice_id,amount) VALUES(?,?,?)""",
            (payment_id, invoice_id, applied))
        conn.execute("""UPDATE customer_account_invoices
            SET paid=?,outstanding=?,status=? WHERE id=?""",
            (new_paid, new_outstanding, status, invoice_id))
        remaining = _money(remaining - applied)

    row = conn.execute("""INSERT INTO customer_account_transactions
        (customer_id,txn_type,reference,description,debit,credit,balance_after,cashier)
        VALUES(?,?,?,?,?,?,?,?)""",
        (customer_id, "PAYMENT", reference or f"PAY-{payment_id:06d}",
         notes or "Customer payment", 0, amount, _money(bal - amount), cashier or "Unknown"))
    return {"payment_id": payment_id, "ledger_id": row.lastrowid,
            "amount": amount, "balance": _money(bal - amount)}


def customer_return_credit(conn, *, customer_id, sale_id, amount, reference,
                           cashier="Unknown", description="Customer return"):
    """Credit a debtor return and reduce its original invoice where possible.

    For an unpaid/part-paid invoice, the invoice outstanding is reduced by the
    return.  This keeps invoice-level balances aligned with the customer ledger.
    If the invoice was already fully paid, the ledger still receives the credit;
    the amount remains an unapplied customer credit rather than inventing a
    negative invoice balance.
    """
    customer_id = int(customer_id)
    sale_id = int(sale_id)
    amount = _money(amount)
    if amount <= 0:
        raise ValueError("Customer return credit must be greater than zero.")

    inv = conn.execute("""SELECT id,total,paid,outstanding FROM customer_account_invoices
                         WHERE customer_id=? AND sale_id=?""", (customer_id, sale_id)).fetchone()
    if inv:
        invoice_id, total, paid, outstanding = inv
        reduce_outstanding = min(amount, _money(outstanding))
        if reduce_outstanding > 0:
            new_total = max(0.0, _money(total) - reduce_outstanding)
            new_outstanding = max(0.0, _money(outstanding) - reduce_outstanding)
            new_paid = min(_money(paid), new_total)
            status = "PAID" if new_outstanding <= 0.005 else ("PART PAID" if new_paid > 0.005 else "UNPAID")
            conn.execute("""UPDATE customer_account_invoices
                SET total=?,paid=?,outstanding=?,status=? WHERE id=?""",
                (new_total, new_paid, new_outstanding, status, invoice_id))

    current = _money(conn.execute(
        "SELECT COALESCE(SUM(debit-credit),0) FROM customer_account_transactions WHERE customer_id=?",
        (customer_id,)).fetchone()[0])
    cur = conn.execute("""INSERT INTO customer_account_transactions
        (customer_id,txn_type,reference,description,debit,credit,balance_after,cashier)
        VALUES(?,?,?,?,?,?,?,?)""",
        (customer_id, "RETURN", reference, description, 0, amount,
         _money(current - amount), cashier or "Unknown"))
    return {"ledger_id": cur.lastrowid, "balance": _money(current - amount)}


def supplier_payment(conn, *, supplier_id, amount, payment_method="Bank Transfer",
                     reference="", notes="", cashier="Unknown", allow_advance=False, payment_date=None):
    """Post a supplier payment and keep the creditor ledger in sync."""
    supplier_id = int(supplier_id)
    amount = _money(amount)
    if amount <= 0:
        raise ValueError("Supplier payment must be greater than zero.")
    has_grn = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='grn_headers'").fetchone()
    has_supplier_id = has_grn and any(r[1]=='supplier_id' for r in conn.execute("PRAGMA table_info(grn_headers)"))
    if has_supplier_id:
        purchase = _money(conn.execute("SELECT COALESCE(SUM(total),0) FROM grn_headers WHERE supplier_id=?", (supplier_id,)).fetchone()[0])
        if purchase == 0.0:
            purchase = _money(conn.execute("SELECT COALESCE(SUM(total_amount),0) FROM account_transactions WHERE account_id=? AND txn_type='PURCHASE'", (supplier_id,)).fetchone()[0])
    else:
        purchase = _money(conn.execute(
            "SELECT COALESCE(SUM(total_amount),0) FROM account_transactions WHERE account_id=? AND txn_type='PURCHASE'",
            (supplier_id,)).fetchone()[0])
    payment = _money(conn.execute(
        "SELECT COALESCE(SUM(total_amount),0) FROM account_transactions WHERE account_id=? AND txn_type='PAYMENT'",
        (supplier_id,)).fetchone()[0])
    credits = 0.0
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='supplier_credits'").fetchone():
        credits = _money(conn.execute("SELECT COALESCE(SUM(amount),0) FROM supplier_credits WHERE supplier_id=?", (supplier_id,)).fetchone()[0])
    outstanding = _money(purchase - payment - credits)
    if not allow_advance and amount > outstanding + 0.01:
        raise ValueError(f"Payment exceeds supplier outstanding balance of R {max(outstanding,0):,.2f}.")

    supplier = conn.execute("SELECT COALESCE(supplier_account_no,''),COALESCE(name,'') FROM accounts WHERE id=?", (supplier_id,)).fetchone()
    if not supplier:
        raise ValueError("Supplier account was not found.")
    account_no, name = supplier
    stamp = payment_date or datetime.now().strftime("%Y-%m-%d")
    cur = conn.execute("""INSERT INTO supplier_payments
        (payment_no,supplier_id,supplier_account_no,supplier_name,payment_date,amount,
         payment_method,reference,notes,cashier,created_by)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
        (reference or f"PAY-{datetime.now().strftime('%Y%m%d%H%M%S%f')}", supplier_id,
         account_no, name, stamp, amount, payment_method or "Bank Transfer", reference or "",
         notes or "", cashier or "Unknown", cashier or "Unknown"))
    payment_id = cur.lastrowid
    cur_txn = conn.execute("INSERT INTO account_transactions(account_id,txn_type,total_amount,txn_date) VALUES(?,?,?,?)",
                           (supplier_id, "PAYMENT", amount, stamp))
    txn_id = cur_txn.lastrowid

    # Allocate the payment FIFO across GRNs. This makes invoice-level balances
    # agree with the supplier control account without changing the legacy ledger.
    grn_cols = {r[1] for r in conn.execute("PRAGMA table_info(grn_headers)")} if has_grn else set()
    if has_grn and {'paid','outstanding','status','supplier_id'}.issubset(grn_cols):
        conn.execute("""CREATE TABLE IF NOT EXISTS supplier_payment_allocations(
            id INTEGER PRIMARY KEY AUTOINCREMENT, payment_id INTEGER NOT NULL,
            grn_id INTEGER NOT NULL, amount REAL NOT NULL CHECK(amount>0),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(payment_id,grn_id))""")
        remaining = amount
        rows = conn.execute("""SELECT id,total,paid,outstanding FROM grn_headers
            WHERE supplier_id=? AND outstanding>0.005 ORDER BY date(created_at),id""", (supplier_id,)).fetchall()
        for grn_id, total, paid_now, outstanding_now in rows:
            if remaining <= 0.005: break
            applied = min(remaining, _money(outstanding_now))
            new_paid = _money(paid_now) + applied
            new_out = max(0.0, _money(total) - new_paid)
            status = 'PAID' if new_out <= 0.005 else ('PART PAID' if new_paid > 0.005 else 'UNPAID')
            conn.execute("INSERT INTO supplier_payment_allocations(payment_id,grn_id,amount) VALUES(?,?,?)",
                         (payment_id, grn_id, applied))
            conn.execute("UPDATE grn_headers SET paid=?,outstanding=?,status=? WHERE id=?",
                         (new_paid,new_out,status,grn_id))
            remaining = _money(remaining - applied)

    return {"payment_id": payment_id, "ledger_id": txn_id, "amount": amount,
            "balance": _money(outstanding - amount)}


def supplier_credit(conn, *, supplier_id, amount, credit_no, credit_date=None,
                    reason="", reference="", created_by="Unknown"):
    """Post a supplier credit against the creditor balance."""
    supplier_id = int(supplier_id)
    amount = _money(amount)
    if amount <= 0:
        raise ValueError("Supplier credit must be greater than zero.")
    if conn.execute("SELECT 1 FROM supplier_credits WHERE credit_no=?", (credit_no,)).fetchone():
        raise ValueError("Supplier credit number already exists.")
    credit_date = credit_date or datetime.now().strftime("%Y-%m-%d")
    cur = conn.execute("""INSERT INTO supplier_credits
        (credit_no,supplier_id,credit_date,amount,reason,reference,created_by)
        VALUES(?,?,?,?,?,?,?)""",
        (credit_no, supplier_id, credit_date, amount, reason, reference, created_by))
    return {"credit_id": cur.lastrowid, "amount": amount}


def void_credit_sale(conn, *, customer_id, sale_id, amount, cashier="Unknown", reference=""):
    """Reverse a credit-sale debtor posting when the sale is voided."""
    customer_id = int(customer_id)
    sale_id = int(sale_id)
    amount = _money(amount)
    if amount <= 0:
        raise ValueError("Voided credit-sale amount must be greater than zero.")

    invoice = conn.execute(
        "SELECT id FROM customer_account_invoices WHERE customer_id=? AND sale_id=?",
        (customer_id, sale_id)
    ).fetchone()
    if invoice:
        conn.execute(
            "UPDATE customer_account_invoices SET total=0, paid=0, outstanding=0, status='VOID' WHERE id=?",
            (invoice[0],)
        )

    current = _money(conn.execute(
        "SELECT COALESCE(SUM(debit-credit),0) FROM customer_account_transactions WHERE customer_id=?",
        (customer_id,)
    ).fetchone()[0])
    cur = conn.execute("""INSERT INTO customer_account_transactions
        (customer_id,txn_type,reference,description,debit,credit,balance_after,cashier)
        VALUES(?,?,?,?,?,?,?,?)""",
        (customer_id, "VOID", reference or f"VOID-{sale_id:06d}",
         "Reversal of voided POS credit sale", 0, amount, _money(current - amount), cashier or "Unknown"))
    return {"ledger_id": cur.lastrowid, "balance": _money(current - amount)}
