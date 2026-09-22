"""Read-only end-of-day reconciliation helpers for BKPOS.

This module does not post transactions. It combines the existing transactional
services into a single, independently testable view of a trading day.
"""
from services.financial_reconciliation import financial_summary, customer_balance, supplier_balance
from services.financial_service import cashup_summary


def business_day_summary(conn, *, date, cashier=None, branch_id=None, opening_float=0.0):
    """Return sales, cash-up, customer/supplier and stock reconciliation data.

    ``cashup_summary`` is the source of truth for drawer cash. The financial
    summary is kept separate because card, credit, VAT and profit are not
    drawer movements.
    """
    financial = financial_summary(conn, start_date=date, end_date=date, branch_id=branch_id)
    cashup = cashup_summary(conn, date=date, cashier=cashier, opening_float=opening_float,
                            branch_id=branch_id)

    stock = conn.execute("""
        SELECT COALESCE(SUM(p.soh),0),
               COALESCE(SUM(CASE WHEN COALESCE(p.soh,0)<0 THEN 1 ELSE 0 END),0)
        FROM products p WHERE COALESCE(p.active,1)=1
    """).fetchone()
    return {
        "financial": financial,
        "cashup": cashup,
        "global_stock_units": round(float(stock[0] or 0), 3),
        "negative_stock_products": int(stock[1] or 0),
    }
