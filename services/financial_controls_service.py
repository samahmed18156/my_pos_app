"""Read-only financial control analytics for BKPOS Phase 4.

These helpers intentionally do not post or mutate accounting transactions. They
provide independently testable control calculations for reconciliation,
ageing and financial exceptions.
"""
from datetime import datetime


def _money(v):
    return round(float(v or 0), 2)


def payment_reconciliation(conn, *, start_date, end_date, branch_id=None):
    """Reconcile completed sales by payment components and flag differences."""
    datetime.strptime(start_date, "%Y-%m-%d")
    datetime.strptime(end_date, "%Y-%m-%d")
    where = "date(timestamp) BETWEEN ? AND ? AND COALESCE(voided,0)=0"
    args = [start_date, end_date]
    if branch_id is not None:
        where += " AND COALESCE(branch_id,1)=?"
        args.append(int(branch_id))
    row = conn.execute(f"""SELECT COALESCE(SUM(total_amount),0),
        COALESCE(SUM(cash_amount),0),COALESCE(SUM(card_amount),0),
        COALESCE(SUM(CASE WHEN lower(COALESCE(payment_type,''))='credit account' THEN total_amount ELSE 0 END),0),
        COUNT(*) FROM sales_history WHERE {where}""", args).fetchone()
    gross, cash, card, credit, txns = map(float, row[:4]) + (int(row[4] or 0),) if False else (float(row[0] or 0), float(row[1] or 0), float(row[2] or 0), float(row[3] or 0), int(row[4] or 0))
    component_total = _money(cash + card + credit)
    return {
        "sales": _money(gross), "cash": _money(cash), "card": _money(card),
        "credit": _money(credit), "components": component_total,
        "difference": _money(component_total - gross), "transactions": txns,
        "status": "OK" if abs(component_total - gross) <= 0.01 else "EXCEPTION",
    }


def cashup_exceptions(conn, *, date, tolerance=0.01, cashier=None):
    """Return submitted cash-ups whose counted cash differs beyond tolerance."""
    args = [date]
    where = "cashup_date=?"
    if cashier:
        where += " AND cashier=?"; args.append(cashier)
    rows = conn.execute(f"""SELECT cashup_date,cashier,opening_float,expected_cash,
        actual_cash,difference FROM cashup_records WHERE {where} ORDER BY cashier""", args).fetchall()
    return [dict(date=r[0], cashier=r[1] or "Unknown", opening_float=_money(r[2]),
                 expected_cash=_money(r[3]), actual_cash=_money(r[4]),
                 difference=_money(r[5]), status="OK" if abs(float(r[5] or 0)) <= tolerance else "EXCEPTION")
            for r in rows]


def customer_ageing(conn, *, as_of):
    """Return customer debtor ageing buckets from open invoices."""
    datetime.strptime(as_of, "%Y-%m-%d")
    rows = conn.execute("""SELECT i.customer_id,COALESCE(c.name,'Customer #'||i.customer_id),
        i.invoice_date,COALESCE(i.outstanding,0)
        FROM customer_account_invoices i
        LEFT JOIN customers c ON c.id=i.customer_id
        WHERE COALESCE(i.outstanding,0)>0.005 AND COALESCE(i.status,'')<>'VOID'
        AND date(i.invoice_date)<=date(?) ORDER BY i.customer_id,i.invoice_date""", (as_of,)).fetchall()
    result=[]
    for customer_id,name,invoice_date,outstanding in rows:
        try: age=(datetime.strptime(as_of,"%Y-%m-%d").date()-datetime.strptime(str(invoice_date)[:10],"%Y-%m-%d").date()).days
        except ValueError: age=0
        bucket="0-30" if age<=30 else "31-60" if age<=60 else "61-90" if age<=90 else "90+"
        result.append((int(customer_id),name or f"Customer #{customer_id}",str(invoice_date),_money(outstanding),age,bucket))
    return result


def supplier_ageing(conn, *, as_of):
    """Return supplier creditor ageing from GRN invoice balances where available."""
    datetime.strptime(as_of, "%Y-%m-%d")
    cols={r[1] for r in conn.execute("PRAGMA table_info(grn_headers)").fetchall()}
    if not {'supplier_id','outstanding'}.issubset(cols):
        return []
    date_col='created_at' if 'created_at' in cols else ('date' if 'date' in cols else None)
    if not date_col: return []
    name_col='supplier_name' if 'supplier_name' in cols else None
    supplier_expr=f"COALESCE(g.{name_col},'Supplier #'||g.supplier_id)" if name_col else "'Supplier #'||g.supplier_id"
    rows=conn.execute(f"""SELECT g.supplier_id,{supplier_expr},g.{date_col},COALESCE(g.outstanding,0)
        FROM grn_headers g WHERE COALESCE(g.outstanding,0)>0.005 AND date(g.{date_col})<=date(?)
        ORDER BY g.supplier_id,g.{date_col}""",(as_of,)).fetchall()
    result=[]
    for sid,name,stamp,outstanding in rows:
        try: age=(datetime.strptime(as_of,"%Y-%m-%d").date()-datetime.strptime(str(stamp)[:10],"%Y-%m-%d").date()).days
        except ValueError: age=0
        bucket="0-30" if age<=30 else "31-60" if age<=60 else "61-90" if age<=90 else "90+"
        result.append((int(sid),name or f"Supplier #{sid}",str(stamp),_money(outstanding),age,bucket))
    return result


def financial_exceptions(conn, *, start_date, end_date):
    """Identify high-value control exceptions without changing any data."""
    issues=[]
    recon=payment_reconciliation(conn,start_date=start_date,end_date=end_date)
    if recon['status']!='OK': issues.append(("PAYMENT", "Payment components do not reconcile", recon['difference']))
    for r in conn.execute("""SELECT id,total_amount,cash_amount,card_amount,payment_type
                           FROM sales_history WHERE date(timestamp) BETWEEN ? AND ? AND COALESCE(voided,0)=0""",(start_date,end_date)).fetchall():
        sid,total,cash,card,pay=r; total=float(total or 0); cash=float(cash or 0); card=float(card or 0)
        if str(pay or '').lower()=='cash' and abs(cash-total)>0.01: issues.append(("SALE",f"Sale #{sid}: cash component mismatch",_money(cash-total)))
        if str(pay or '').lower()=='card' and abs(card-total)>0.01: issues.append(("SALE",f"Sale #{sid}: card component mismatch",_money(card-total)))
    for r in cashup_exceptions(conn,date=end_date):
        if r['status']!='OK': issues.append(("CASHUP",f"{r['cashier']} cash-up variance",r['difference']))
    return issues
