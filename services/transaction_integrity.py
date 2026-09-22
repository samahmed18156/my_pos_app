"""BKPOS Phase 48 — financial and stock transaction invariants.

These assertions are intentionally read-only. They give service/UI code and
automated tests a common way to prove that a posted document is internally
consistent before the surrounding transaction is committed.
"""
from __future__ import annotations


def _money(value):
    return round(float(value or 0), 2)


def assert_sale_integrity(conn, sale_id: int, tolerance: float = 0.02) -> None:
    sale = conn.execute(
        "SELECT total_amount,total_cost FROM sales_history WHERE id=?", (int(sale_id),)
    ).fetchone()
    if not sale:
        raise AssertionError(f"Sale {sale_id} does not exist")
    total, cogs = map(_money, sale)
    lines = conn.execute(
        "SELECT COALESCE(SUM(value),0), COALESCE(SUM(qty*COALESCE(cost_price,0)),0) "
        "FROM sale_items WHERE sale_id=?", (int(sale_id),)
    ).fetchone()
    line_total, line_cogs = map(_money, lines)
    if abs(total - line_total) > tolerance:
        raise AssertionError(f"Sale {sale_id}: header total {total:.2f} != lines {line_total:.2f}")
    if abs(cogs - line_cogs) > tolerance:
        raise AssertionError(f"Sale {sale_id}: header COGS {cogs:.2f} != lines {line_cogs:.2f}")


def assert_grn_integrity(conn, grn_id: int, tolerance: float = 0.02) -> None:
    row = conn.execute(
        "SELECT subtotal,vat,total FROM grn_headers WHERE id=?", (int(grn_id),)
    ).fetchone()
    if not row:
        raise AssertionError(f"GRN {grn_id} does not exist")
    subtotal, vat, total = map(_money, row)
    line_total = _money(conn.execute(
        "SELECT COALESCE(SUM(value),0) FROM grn_items WHERE grn_id=?", (int(grn_id),)
    ).fetchone()[0])
    if abs(line_total - total) > tolerance and abs(line_total - (subtotal + vat)) > tolerance:
        raise AssertionError(
            f"GRN {grn_id}: lines {line_total:.2f} do not reconcile to total {total:.2f} "
            f"or subtotal+VAT {subtotal+vat:.2f}"
        )
    if abs((subtotal + vat) - total) > tolerance:
        raise AssertionError(f"GRN {grn_id}: subtotal+VAT {subtotal+vat:.2f} != total {total:.2f}")


def assert_customer_invoice_integrity(conn, invoice_id: int, tolerance: float = 0.02) -> None:
    row = conn.execute(
        "SELECT total,paid,outstanding,status FROM customer_account_invoices WHERE id=?",
        (int(invoice_id),),
    ).fetchone()
    if not row:
        raise AssertionError(f"Customer invoice {invoice_id} does not exist")
    total, paid, outstanding, status = row
    if str(status).upper() == "VOID":
        if any(abs(_money(v)) > tolerance for v in (total, paid, outstanding)):
            raise AssertionError(f"Voided customer invoice {invoice_id} has non-zero balances")
        return
    expected = max(0.0, _money(total) - _money(paid))
    if abs(_money(outstanding) - expected) > tolerance:
        raise AssertionError(
            f"Customer invoice {invoice_id}: outstanding {_money(outstanding):.2f} != "
            f"total-paid {expected:.2f}"
        )


def assert_supplier_grn_integrity(conn, grn_id: int, tolerance: float = 0.02) -> None:
    row = conn.execute(
        "SELECT total,paid,outstanding,status FROM grn_headers WHERE id=?", (int(grn_id),)
    ).fetchone()
    if not row:
        raise AssertionError(f"Supplier GRN {grn_id} does not exist")
    total, paid, outstanding, status = row
    expected = max(0.0, _money(total) - _money(paid))
    if abs(_money(outstanding) - expected) > tolerance:
        raise AssertionError(
            f"Supplier GRN {grn_id}: outstanding {_money(outstanding):.2f} != total-paid {expected:.2f}"
        )
    expected_status = "PAID" if expected <= tolerance else ("PART PAID" if _money(paid) > tolerance else "UNPAID")
    if str(status).upper() != expected_status:
        raise AssertionError(f"Supplier GRN {grn_id}: status {status!r} != {expected_status!r}")


def assert_stock_movement_integrity(conn, movement_id: int, tolerance: float = 1e-9) -> None:
    row = conn.execute(
        "SELECT qty_before,qty_after,qty FROM stock_movements WHERE id=?", (int(movement_id),)
    ).fetchone()
    if not row:
        raise AssertionError(f"Stock movement {movement_id} does not exist")
    before, after, qty = (float(v or 0) for v in row)
    if abs((before + qty) - after) > tolerance:
        raise AssertionError(
            f"Stock movement {movement_id}: before {before:g} + qty {qty:g} != after {after:g}"
        )
