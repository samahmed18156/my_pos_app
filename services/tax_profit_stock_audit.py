"""VAT, profit and stock valuation reconciliation for BKPOS.

The audit is read-only. It uses the transaction values actually stored by BKPOS
and makes the tax basis explicit instead of silently guessing.
"""
from __future__ import annotations

VAT_RATE = 0.15
VAT_DIVISOR = 1.15


def _money(value):
    return round(float(value or 0), 2)


def _sum(conn, sql, args=()):
    row = conn.execute(sql, args).fetchone()
    return float(row[0] or 0) if row else 0.0


def _period(clauses, args, column, start_date, end_date):
    if start_date:
        clauses.append(f"DATE({column})>=DATE(?)"); args.append(start_date)
    if end_date:
        clauses.append(f"DATE({column})<=DATE(?)"); args.append(end_date)


def sales_tax(conn, *, start_date=None, end_date=None, branch_id=None):
    clauses = ["COALESCE(voided,0)=0"]; args = []
    _period(clauses, args, "timestamp", start_date, end_date)
    if branch_id is not None:
        clauses.append("COALESCE(branch_id,1)=?"); args.append(int(branch_id))
    where = " AND ".join(clauses)
    gross = _sum(conn, f"SELECT SUM(total_amount) FROM sales_history WHERE {where}", args)
    returns_clauses = ["1=1"]; returns_args = []
    _period(returns_clauses, returns_args, "r.timestamp", start_date, end_date)
    if branch_id is not None:
        returns_clauses.append("COALESCE(s.branch_id,1)=?"); returns_args.append(int(branch_id))
    returns = _sum(conn, f"""SELECT SUM(r.total_amount) FROM return_history r
        JOIN sales_history s ON s.id=r.original_sale_id
        WHERE {' AND '.join(returns_clauses)}""", returns_args)
    net_inclusive = max(0.0, gross - returns)
    output_vat = net_inclusive * VAT_RATE / VAT_DIVISOR
    return {"gross_inclusive": _money(gross), "returns_inclusive": _money(returns),
            "net_inclusive": _money(net_inclusive), "output_vat": _money(output_vat),
            "net_sales_ex_vat": _money(net_inclusive - output_vat)}


def purchase_tax(conn, *, start_date=None, end_date=None, branch_id=None):
    clauses = ["1=1"]; args = []
    _period(clauses, args, "created_at", start_date, end_date)
    if branch_id is not None:
        # grn_headers currently has no branch_id in older databases. If present,
        # filter it; otherwise the purchase is treated as global.
        cols = {r[1] for r in conn.execute("PRAGMA table_info(grn_headers)")}
        if "branch_id" in cols:
            clauses.append("COALESCE(branch_id,1)=?"); args.append(int(branch_id))
    rows = conn.execute(f"SELECT COALESCE(total,0),COALESCE(subtotal,0),COALESCE(vat,0),LOWER(COALESCE(vat_mode,'inclusive')) FROM grn_headers WHERE {' AND '.join(clauses)}", args).fetchall()
    total = sum(float(r[0] or 0) for r in rows)
    recorded_subtotal = sum(float(r[1] or 0) for r in rows)
    input_vat = sum(float(r[2] or 0) for r in rows)
    credits_clauses = ["1=1"]; credits_args = []
    _period(credits_clauses, credits_args, "sc.credit_date", start_date, end_date)
    if branch_id is not None:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(supplier_credits)")}
        if "branch_id" in cols:
            credits_clauses.append("COALESCE(sc.branch_id,1)=?"); credits_args.append(int(branch_id))
    credit_rows = conn.execute(f"""SELECT COALESCE(sci.value,0), LOWER(COALESCE(gh.vat_mode,'inclusive'))
        FROM supplier_credit_items sci JOIN supplier_credits sc ON sc.id=sci.credit_id
        LEFT JOIN grn_headers gh ON gh.id=sci.grn_id
        WHERE {' AND '.join(credits_clauses)}""", credits_args).fetchall() if "supplier_credit_items" in {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")} else []
    credit_total = sum(float(r[0] or 0) for r in credit_rows)
    credit_vat = 0.0
    for value, mode in credit_rows:
        credit_vat += value * VAT_RATE / VAT_DIVISOR if mode == "inclusive" else value * VAT_RATE
    # GRN subtotal is stored ex-VAT for inclusive purchases and as entered for exclusive purchases.
    purchase_net = sum(float(r[1] or 0) for r in rows)
    return {"purchases_inclusive_or_total": _money(total), "purchase_net_ex_vat": _money(purchase_net),
            "input_vat": _money(input_vat), "supplier_credits_total": _money(credit_total),
            "supplier_credit_vat": _money(credit_vat),
            "net_purchases_ex_vat": _money(purchase_net - credit_total + credit_vat)}


def expense_tax(conn, *, start_date=None, end_date=None, branch_id=None):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "operating_expenses" not in tables:
        return {"expenses_total": 0.0, "expense_vat": 0.0, "expenses_ex_vat": 0.0}
    clauses=["1=1"]; args=[]
    _period(clauses,args,"expense_date",start_date,end_date)
    if branch_id is not None:
        clauses.append("COALESCE(branch_id,1)=?"); args.append(int(branch_id))
    row=conn.execute(f"SELECT COALESCE(SUM(total_amount),0),COALESCE(SUM(vat_amount),0),COALESCE(SUM(amount_ex_vat),0) FROM operating_expenses WHERE {' AND '.join(clauses)}",args).fetchone()
    return {"expenses_total":_money(row[0]),"expense_vat":_money(row[1]),"expenses_ex_vat":_money(row[2])}


def stock_valuation(conn):
    global_value = _sum(conn, "SELECT SUM(COALESCE(soh,0)*COALESCE(cost_price,0)) FROM products")
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    branch_value = 0.0
    if "branch_stock" in tables:
        branch_value = _sum(conn, """SELECT SUM(COALESCE(bs.soh,0)*COALESCE(p.cost_price,0))
            FROM branch_stock bs JOIN products p ON p.barcode=bs.barcode""")
    qty_global = _sum(conn, "SELECT SUM(COALESCE(soh,0)) FROM products")
    qty_branch = _sum(conn, "SELECT SUM(COALESCE(soh,0)) FROM branch_stock") if "branch_stock" in tables else qty_global
    return {"global_value":_money(global_value),"branch_value":_money(branch_value),
            "value_difference":_money(global_value-branch_value),
            "global_units":_money(qty_global),"branch_units":_money(qty_branch),
            "units_difference":_money(qty_global-qty_branch),
            "valuation_method":"Perpetual weighted-average cost (product SOH × moving-average cost)"}


def audit(conn, *, start_date=None, end_date=None, branch_id=None):
    sales=sales_tax(conn,start_date=start_date,end_date=end_date,branch_id=branch_id)
    purchases=purchase_tax(conn,start_date=start_date,end_date=end_date,branch_id=branch_id)
    expenses=expense_tax(conn,start_date=start_date,end_date=end_date,branch_id=branch_id)
    stock=stock_valuation(conn)
    # BKPOS records selling prices and GRN costs as VAT-inclusive by default.
    # COGS therefore needs the same conversion when the recorded cost is VAT-inclusive.
    clauses=["COALESCE(voided,0)=0"]; args=[]
    _period(clauses,args,"timestamp",start_date,end_date)
    if branch_id is not None: clauses.append("COALESCE(branch_id,1)=?"); args.append(int(branch_id))
    recorded_cogs=_sum(conn,f"SELECT SUM(total_cost) FROM sales_history WHERE {' AND '.join(clauses)}",args)
    # Returned cost is based on the product cost stored at audit time; report it explicitly.
    rclauses=["1=1"]; rargs=[]; _period(rclauses,rargs,"r.timestamp",start_date,end_date)
    if branch_id is not None: rclauses.append("COALESCE(s.branch_id,1)=?"); rargs.append(int(branch_id))
    returned_cogs=_sum(conn,f"""SELECT SUM(ri.qty*COALESCE(p.cost_price,0)) FROM return_items ri
        JOIN return_history r ON r.id=ri.return_id JOIN sales_history s ON s.id=r.original_sale_id
        LEFT JOIN products p ON p.barcode=ri.barcode WHERE {' AND '.join(rclauses)}""",rargs)
    net_recorded_cogs=max(0.0,recorded_cogs-returned_cogs)
    cogs_ex_vat=net_recorded_cogs/VAT_DIVISOR
    gross_profit=sales["net_sales_ex_vat"]-cogs_ex_vat
    net_profit=gross_profit-expenses["expenses_ex_vat"]
    vat_payable=max(0.0,sales["output_vat"]-purchases["input_vat"]+purchases["supplier_credit_vat"]-expenses["expense_vat"])
    return {"sales":sales,"purchases":purchases,"expenses":expenses,"stock":stock,
            "recorded_cogs_inclusive":_money(net_recorded_cogs),"cogs_ex_vat":_money(cogs_ex_vat),
            "gross_profit_ex_vat":_money(gross_profit),"net_profit_ex_vat":_money(net_profit),
            "vat_payable_before_adjustments":_money(vat_payable),
            "stock_balanced":abs(stock["value_difference"])<0.01 and abs(stock["units_difference"])<0.01}
