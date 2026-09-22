"""Read-only financial reconciliation helpers for BKPOS.

These functions intentionally do not mutate the database. They provide one
place for tests and future reports to calculate the same financial figures.
Selling prices are VAT-inclusive at 15% unless stated otherwise.
"""

VAT_RATE = 0.15
VAT_DIVISOR = 1.0 + VAT_RATE


def _sum(conn, sql, args=()):
    row = conn.execute(sql, args).fetchone()
    return float(row[0] or 0) if row else 0.0


def sales_summary(conn, *, start_date=None, end_date=None, branch_id=None):
    clauses = ["COALESCE(voided,0)=0"]
    args = []
    if start_date:
        clauses.append("DATE(timestamp)>=DATE(?)"); args.append(start_date)
    if end_date:
        clauses.append("DATE(timestamp)<=DATE(?)"); args.append(end_date)
    if branch_id is not None:
        clauses.append("COALESCE(branch_id,1)=?"); args.append(int(branch_id))
    where = " AND ".join(clauses)
    gross = conn.execute(f"""
        SELECT COALESCE(SUM(total_amount),0), COALESCE(SUM(total_cost),0),
               COALESCE(SUM(cash_amount),0), COALESCE(SUM(card_amount),0), COUNT(*)
        FROM sales_history WHERE {where}
    """, args).fetchone()
    gross_sales, cogs, cash, card, transactions = [float(x or 0) for x in gross]
    vat = gross_sales * VAT_RATE / VAT_DIVISOR
    net_sales = gross_sales - vat
    gross_profit = gross_sales - cogs
    return {
        "gross_sales": round(gross_sales, 2), "vat": round(vat, 2),
        "net_sales": round(net_sales, 2), "cost_of_goods": round(cogs, 2),
        "gross_profit": round(gross_profit, 2), "cash_sales": round(cash, 2),
        "card_sales": round(card, 2), "transactions": int(transactions),
    }


def returns_summary(conn, *, start_date=None, end_date=None, branch_id=None):
    clauses = ["1=1"]; args=[]
    if start_date: clauses.append("DATE(r.timestamp)>=DATE(?)"); args.append(start_date)
    if end_date: clauses.append("DATE(r.timestamp)<=DATE(?)"); args.append(end_date)
    # Returns are tied to the original sale branch, not the screen's branch.
    if branch_id is not None:
        clauses.append("COALESCE(s.branch_id,1)=?"); args.append(int(branch_id))
    row = conn.execute(f"""
        SELECT COALESCE(SUM(r.total_amount),0), COUNT(*)
        FROM return_history r JOIN sales_history s ON s.id=r.original_sale_id
        WHERE {' AND '.join(clauses)}
    """, args).fetchone()
    return {"returns": round(float(row[0] or 0),2), "return_transactions": int(row[1] or 0)}


def expense_summary(conn, *, start_date=None, end_date=None, branch_id=None):
    # Prefer the structured operating_expenses table when present; fall back to
    # the legacy expenses table used by the original Utility screen.
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "operating_expenses" in tables:
        clauses=["1=1"]; args=[]
        if start_date: clauses.append("DATE(expense_date)>=DATE(?)"); args.append(start_date)
        if end_date: clauses.append("DATE(expense_date)<=DATE(?)"); args.append(end_date)
        if branch_id is not None: clauses.append("COALESCE(branch_id,1)=?"); args.append(int(branch_id))
        amount = _sum(conn, f"SELECT COALESCE(SUM(total_amount),0) FROM operating_expenses WHERE {' AND '.join(clauses)}", args)
        vat = _sum(conn, f"SELECT COALESCE(SUM(vat_amount),0) FROM operating_expenses WHERE {' AND '.join(clauses)}", args)
        return {"expenses": round(amount,2), "expense_vat": round(vat,2)}
    if "expenses" in tables:
        clauses=["1=1"]; args=[]
        if start_date: clauses.append("DATE(date_logged)>=DATE(?)"); args.append(start_date)
        if end_date: clauses.append("DATE(date_logged)<=DATE(?)"); args.append(end_date)
        amount = _sum(conn, f"SELECT COALESCE(SUM(amount),0) FROM expenses WHERE {' AND '.join(clauses)}", args)
        return {"expenses": round(amount,2), "expense_vat": 0.0}
    return {"expenses": 0.0, "expense_vat": 0.0}


def financial_summary(conn, *, start_date=None, end_date=None, branch_id=None):
    sales = sales_summary(conn, start_date=start_date, end_date=end_date, branch_id=branch_id)
    returns = returns_summary(conn, start_date=start_date, end_date=end_date, branch_id=branch_id)
    expenses = expense_summary(conn, start_date=start_date, end_date=end_date, branch_id=branch_id)
    # Returned selling value reduces sales/profit; the COGS portion is restored
    # with returned stock, so gross profit is reduced by the gross margin of the
    # returned goods. We calculate that margin from returned sale lines.
    clauses=["COALESCE(s.voided,0)=0"]; args=[]
    if start_date: clauses.append("DATE(r.timestamp)>=DATE(?)"); args.append(start_date)
    if end_date: clauses.append("DATE(r.timestamp)<=DATE(?)"); args.append(end_date)
    if branch_id is not None: clauses.append("COALESCE(s.branch_id,1)=?"); args.append(int(branch_id))
    returned_cost = _sum(conn, f"""
        SELECT COALESCE(SUM(ri.qty * COALESCE(p.cost_price,0)),0)
        FROM return_items ri
        JOIN return_history r ON r.id=ri.return_id
        JOIN sales_history s ON s.id=r.original_sale_id
        LEFT JOIN products p ON p.barcode=ri.barcode
        WHERE {' AND '.join(clauses)}
    """, args)
    net_sales = sales["gross_sales"] - returns["returns"]
    net_vat = max(0.0, net_sales * VAT_RATE / VAT_DIVISOR)
    net_cogs = max(0.0, sales["cost_of_goods"] - returned_cost)
    gross_profit = net_sales - net_cogs
    net_profit = gross_profit - expenses["expenses"]
    return {
        **sales, **returns, **expenses,
        "returned_cost": round(returned_cost,2), "net_sales": round(net_sales,2),
        "vat": round(net_vat,2), "cost_of_goods": round(net_cogs,2),
        "gross_profit": round(gross_profit,2), "net_profit": round(net_profit,2),
    }


def customer_balance(conn, customer_id):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "customer_account_transactions" in tables:
        # The existing customer ledger uses debit for invoices and credit for payments/returns.
        debit = _sum(conn, "SELECT COALESCE(SUM(debit),0) FROM customer_account_transactions WHERE customer_id=?", (customer_id,))
        credit = _sum(conn, "SELECT COALESCE(SUM(credit),0) FROM customer_account_transactions WHERE customer_id=?", (customer_id,))
        return round(debit-credit,2)
    return 0.0


def supplier_balance(conn, supplier_id):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "grn_headers" in tables:
        purchase = _sum(conn, "SELECT COALESCE(SUM(total),0) FROM grn_headers WHERE supplier_id=?", (supplier_id,)) if any(r[1]=='supplier_id' for r in conn.execute("PRAGMA table_info(grn_headers)")) else 0.0
        if purchase == 0.0:
            purchase = _sum(conn, "SELECT COALESCE(SUM(total_amount),0) FROM account_transactions WHERE account_id=? AND txn_type='PURCHASE'", (supplier_id,))
    else:
        purchase = _sum(conn, "SELECT COALESCE(SUM(total_amount),0) FROM account_transactions WHERE account_id=? AND txn_type='PURCHASE'", (supplier_id,))
    payment = _sum(conn, "SELECT COALESCE(SUM(amount),0) FROM supplier_payments WHERE supplier_id=?", (supplier_id,)) if "supplier_payments" in tables else _sum(conn, "SELECT COALESCE(SUM(total_amount),0) FROM account_transactions WHERE account_id=? AND txn_type='PAYMENT'", (supplier_id,))
    credit = _sum(conn, "SELECT COALESCE(SUM(amount),0) FROM supplier_credits WHERE supplier_id=?", (supplier_id,)) if "supplier_credits" in tables else 0.0
    return round(purchase-payment-credit,2)
