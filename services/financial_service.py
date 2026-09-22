"""Financial control transactions that can be tested without Tkinter."""
from services.branch_stock_service import get_branch_soh, change_stock
from services.stock_service import record_stock_movement


def void_sale(conn, sale_id, *, actor="Unknown", reason="Sale voided"):
    sale = conn.execute("""SELECT total_amount,cash_amount,card_amount,payment_type,cashier,
                                 COALESCE(voided,0),COALESCE(branch_id,1),customer_id
                          FROM sales_history WHERE id=?""", (int(sale_id),)).fetchone()
    if not sale:
        raise ValueError("Invoice was not found.")
    total,cash_amt,card_amt,payment_type,cashier,voided,sale_branch,customer_id = sale
    if voided:
        raise ValueError("This invoice is already voided.")
    items = conn.execute("SELECT id,barcode,description,qty FROM sale_items WHERE sale_id=?", (int(sale_id),)).fetchall()
    restored = 0.0
    for item_id, code, desc, qty in items:
        already = conn.execute("SELECT COALESCE(SUM(qty),0) FROM return_items WHERE sale_item_id=?", (item_id,)).fetchone()[0] or 0
        restore = max(0.0, float(qty or 0) - float(already or 0))
        if restore <= 0:
            continue
        row = conn.execute("SELECT COALESCE(cost_price,0),description FROM products WHERE barcode=?", (code,)).fetchone()
        if not row:
            raise ValueError(f"Product {code} is missing from Products.")
        before = get_branch_soh(conn, sale_branch, code)
        _, after = change_stock(conn, sale_branch, code, restore, expected_before=before)
        record_stock_movement(code, "VOID", restore, reference=f"VOID SALE #{sale_id}",
                              description=desc or row[1] or code, qty_before=before, qty_after=after,
                              cost_price=float(row[0] or 0), reason=reason, cashier=actor, conn=conn)
        restored += restore
    # A voided credit sale must also reverse its debtor posting. Otherwise the
    # stock is restored and the sale disappears from reports while the customer
    # is still left owing the original invoice. Reverse the original sale debit
    # in full; any prior customer payments therefore become a customer credit,
    # which is the only accounting outcome that does not silently lose money.
    if customer_id and str(payment_type or "") == "Credit Account":
        from services.accounts_service import void_credit_sale
        void_credit_sale(conn, customer_id=int(customer_id), sale_id=int(sale_id),
                         amount=float(total or 0), cashier=actor,
                         reference=f"VOID-{int(sale_id):06d}")

    if customer_id:
        from services.loyalty_service import reverse_sale
        reverse_sale(conn, int(customer_id), int(sale_id), reason="Points reversed because sale was voided")

    conn.execute("UPDATE sales_history SET voided=1,voided_at=datetime('now','localtime'),voided_by=? WHERE id=?", (actor,int(sale_id)))
    conn.execute("""INSERT INTO void_history(sale_id,amount,cash_amount,card_amount,cashier,reason)
                   VALUES(?,?,?,?,?,?)""", (int(sale_id),float(total or 0),float(cash_amt or 0),float(card_amt or 0),actor,reason))
    conn.execute("""INSERT INTO transaction_controls(control_type,reference,amount,status,notes,cashier)
                   VALUES(?,?,?,?,?,?)""", ("VOID",f"SALE #{sale_id}",float(total or 0),"OK",reason,actor))
    return {"sale_id": int(sale_id), "total": round(float(total or 0),2), "restored_qty": restored}


def cashup_summary(conn, *, date, cashier=None, opening_float=0.0, branch_id=None):
    where = "DATE(timestamp)=? AND COALESCE(voided,0)=0"
    args = [date]
    if cashier:
        where += " AND cashier=?"
        args.append(cashier)
    if branch_id is not None:
        where += " AND COALESCE(branch_id,1)=?"
        args.append(int(branch_id))
    sales = conn.execute(f"SELECT COALESCE(SUM(total_amount),0),COALESCE(SUM(cash_amount),0),COALESCE(SUM(card_amount),0),COUNT(*) FROM sales_history WHERE {where}", args).fetchone()
    refund_args = [date]
    refund_where = "DATE(timestamp)=? AND lower(refund_type)='cash refund'"
    if cashier:
        refund_where += " AND cashier=?"; refund_args.append(cashier)
    if branch_id is not None:
        refund_where += " AND EXISTS (SELECT 1 FROM sales_history s WHERE s.id=return_history.original_sale_id AND COALESCE(s.branch_id,1)=?)"
        refund_args.append(int(branch_id))
    refunds = conn.execute(f"SELECT COALESCE(SUM(total_amount),0) FROM return_history WHERE {refund_where}", refund_args).fetchone()[0] or 0
    gross = float(sales[0] or 0)
    cash = float(sales[1] or 0)
    card = float(sales[2] or 0)
    count = int(sales[3] or 0)
    # Cash paid out during the day must also leave the drawer. Supplier payments
    # and operating expenses are included only when their payment method is Cash.
    payout = 0.0
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "supplier_payments" in tables and "account_transactions" in tables:
        q = "SELECT COALESCE(SUM(sp.amount),0) FROM supplier_payments sp WHERE DATE(sp.payment_date)=? AND lower(sp.payment_method)='cash'"
        a = [date]
        if cashier: q += " AND sp.cashier=?"; a.append(cashier)
        payout += float(conn.execute(q, a).fetchone()[0] or 0)
    if "operating_expenses" in tables:
        q = "SELECT COALESCE(SUM(total_amount),0) FROM operating_expenses WHERE DATE(expense_date)=? AND lower(payment_method)='cash'"
        a = [date]
        if branch_id is not None: q += " AND COALESCE(branch_id,1)=?"; a.append(int(branch_id))
        if cashier: q += " AND COALESCE(captured_by,'Unknown')=?"; a.append(cashier)
        payout += float(conn.execute(q, a).fetchone()[0] or 0)
    expected = float(opening_float) + cash - float(refunds) - payout
    return {"gross_sales":gross,"cash_sales":cash,"card_sales":card,"transactions":count,
            "cash_refunds":float(refunds),"cash_payouts":round(payout,2),"expected_cash":expected}
