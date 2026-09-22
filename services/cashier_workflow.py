"""BKPOS Phase 66 — cashier workflow and cash-drawer controls.

This service provides the operational rules needed for a real cashier shift:
opening float, one active shift per cashier, controlled cash-in/out entries,
shift-scoped expected cash and a safe close operation.  It deliberately does
not post sales or accounting transactions itself; it reconciles the existing
ledgers.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime

from services.cashup_hardening import ensure_schema as ensure_cashup_schema, validate_cashup


def _table_exists(conn, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def ensure_schema(conn) -> None:
    """Create Phase 66 drawer structures without deleting existing data."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cash_drawer_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shift_id INTEGER NOT NULL,
            movement_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            movement_type TEXT NOT NULL CHECK (movement_type IN ('PAY_IN','PAY_OUT')),
            amount REAL NOT NULL CHECK (amount > 0),
            reference TEXT DEFAULT '',
            reason TEXT DEFAULT '',
            cashier TEXT NOT NULL
        )
    """)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(cashup_records)").fetchall()} if _table_exists(conn, "cashup_records") else set()
    if cols and "shift_id" not in cols:
        conn.execute("ALTER TABLE cashup_records ADD COLUMN shift_id INTEGER")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cash_drawer_movements_shift_time ON cash_drawer_movements(shift_id, movement_time)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cash_drawer_movements_cashier_time ON cash_drawer_movements(cashier, movement_time)")


def _parse_amount(value) -> float:
    amount = float(value)
    if amount <= 0:
        raise ValueError("Cash amount must be greater than zero.")
    return round(amount, 2)


def get_open_shift(conn, cashier: str):
    ensure_schema(conn)
    return conn.execute(
        "SELECT id,cashier,opened_at,opening_cash,closed_at,closing_cash,expected_cash,difference,status "
        "FROM cashier_shifts WHERE cashier=? AND status='OPEN' ORDER BY id DESC LIMIT 1",
        (cashier,),
    ).fetchone()


def open_shift(conn, *, cashier: str, opening_cash) -> int:
    cashier = str(cashier or "").strip()
    if not cashier:
        raise ValueError("Cashier is required.")
    opening = float(opening_cash)
    if opening < 0:
        raise ValueError("Opening cash cannot be negative.")
    ensure_schema(conn)
    ensure_cashup_schema(conn)
    if get_open_shift(conn, cashier):
        raise ValueError(f"Cashier {cashier} already has an open shift.")
    cur = conn.execute(
        "INSERT INTO cashier_shifts(cashier,opened_at,opening_cash,status) VALUES (?,datetime('now','localtime'),?,'OPEN')",
        (cashier, opening),
    )
    return int(cur.lastrowid)


def record_cash_movement(conn, *, shift_id: int, cashier: str, movement_type: str,
                         amount, reference: str = "", reason: str = "") -> int:
    movement_type = str(movement_type or "").upper().strip()
    if movement_type not in {"PAY_IN", "PAY_OUT"}:
        raise ValueError("Movement type must be PAY_IN or PAY_OUT.")
    row = conn.execute(
        "SELECT id,cashier,status FROM cashier_shifts WHERE id=?", (int(shift_id),)
    ).fetchone()
    if not row or row[1] != cashier or row[2] != "OPEN":
        raise ValueError("The selected cashier shift is not open.")
    amount = _parse_amount(amount)
    if movement_type == "PAY_OUT" and not str(reason or "").strip():
        raise ValueError("A reason is required for a cash payout.")
    cur = conn.execute(
        "INSERT INTO cash_drawer_movements(shift_id,movement_time,movement_type,amount,reference,reason,cashier) "
        "VALUES (?,datetime('now','localtime'),?,?,?,?,?)",
        (int(shift_id), movement_type, amount, str(reference or "").strip(), str(reason or "").strip(), cashier),
    )
    return int(cur.lastrowid)


def _shift_window(shift):
    return shift[2], (shift[4] if shift[4] else datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def shift_cash_summary(conn, shift_id: int) -> dict:
    """Reconcile all identifiable cash activity inside one shift window."""
    ensure_schema(conn)
    shift = conn.execute(
        "SELECT id,cashier,opened_at,opening_cash,closed_at FROM cashier_shifts WHERE id=?", (int(shift_id),)
    ).fetchone()
    if not shift:
        raise ValueError("Shift was not found.")
    sid, cashier, start, opening, end = shift
    finish = end or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def one(sql, args=()):
        return float(conn.execute(sql, args).fetchone()[0] or 0)

    sales = one("""SELECT COALESCE(SUM(CASE WHEN cash_amount>0 THEN cash_amount
                     WHEN lower(payment_type)='cash' THEN total_amount ELSE 0 END),0)
                  FROM sales_history WHERE cashier=? AND datetime(timestamp)>=datetime(?) AND datetime(timestamp)<=datetime(?)
                    AND COALESCE(voided,0)=0 AND COALESCE(status,'COMPLETED')='COMPLETED'""", (cashier,start,finish))
    refunds = one("""SELECT COALESCE(SUM(total_amount),0) FROM return_history
                   WHERE cashier=? AND lower(refund_type)='cash refund'
                     AND datetime(timestamp)>=datetime(?) AND datetime(timestamp)<=datetime(?)""", (cashier,start,finish)) if _table_exists(conn,"return_history") else 0.0
    customer_payments = one("""SELECT COALESCE(SUM(amount),0) FROM customer_account_payments
                              WHERE cashier=? AND lower(payment_method)='cash'
                                AND datetime(payment_date)>=datetime(?) AND datetime(payment_date)<=datetime(?)""", (cashier,start,finish)) if _table_exists(conn,"customer_account_payments") else 0.0
    supplier_payouts = one("""SELECT COALESCE(SUM(amount),0) FROM supplier_payments
                             WHERE cashier=? AND lower(payment_method)='cash'
                               AND datetime(payment_date)>=datetime(?) AND datetime(payment_date)<=datetime(?)""", (cashier,start,finish)) if _table_exists(conn,"supplier_payments") else 0.0
    expenses = one("""SELECT COALESCE(SUM(total_amount),0) FROM operating_expenses
                     WHERE COALESCE(captured_by,'Unknown')=? AND lower(payment_method)='cash'
                       AND datetime(expense_date)>=datetime(?) AND datetime(expense_date)<=datetime(?)""", (cashier,start,finish)) if _table_exists(conn,"operating_expenses") else 0.0
    pay_in = one("SELECT COALESCE(SUM(amount),0) FROM cash_drawer_movements WHERE shift_id=? AND movement_type='PAY_IN'", (sid,))
    pay_out = one("SELECT COALESCE(SUM(amount),0) FROM cash_drawer_movements WHERE shift_id=? AND movement_type='PAY_OUT'", (sid,))
    expected = float(opening or 0) + sales + customer_payments + pay_in - refunds - supplier_payouts - expenses - pay_out
    return {
        "shift_id": sid, "cashier": cashier, "opened_at": start, "closed_at": end,
        "opening_cash": round(float(opening or 0),2), "cash_sales": round(sales,2),
        "customer_cash_payments": round(customer_payments,2), "cash_refunds": round(refunds,2),
        "supplier_cash_payouts": round(supplier_payouts,2), "cash_expenses": round(expenses,2),
        "cash_pay_ins": round(pay_in,2), "cash_pay_outs": round(pay_out,2),
        "expected_cash": round(expected,2),
    }


def close_shift(conn, *, shift_id: int, actual_cash, denomination_counts=None, variance_reason="", approved_by="", approval_note="") -> dict:
    shift = conn.execute("SELECT id,cashier,status FROM cashier_shifts WHERE id=?", (int(shift_id),)).fetchone()
    if not shift:
        raise ValueError("Shift was not found.")
    if shift[2] != "OPEN":
        raise ValueError("This shift is already closed.")
    summary = shift_cash_summary(conn, int(shift_id))
    validated = validate_cashup(expected_cash=summary["expected_cash"], actual_cash=actual_cash,
                                denomination_counts=denomination_counts, variance_reason=variance_reason,
                                approved_by=approved_by)
    actual = validated["actual_cash"]; diff = validated["difference"]
    cur = conn.execute("""UPDATE cashier_shifts SET closed_at=datetime('now','localtime'),closing_cash=?,
                    expected_cash=?,difference=?,status='CLOSED' WHERE id=? AND status='OPEN'""",
                 (actual, summary["expected_cash"], diff, int(shift_id)))
    if cur.rowcount != 1:
        raise ValueError("This shift could not be closed because its status changed. Refresh and try again.")
    if _table_exists(conn, "cashup_records"):
        cols = {r[1] for r in conn.execute("PRAGMA table_info(cashup_records)").fetchall()}
        if "shift_id" in cols:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(cashup_records)").fetchall()}
            if {"counted_at", "count_json", "variance_reason", "approved_by", "approval_note"}.issubset(cols):
                conn.execute("INSERT INTO cashup_records(cashup_date,cashier,opening_float,expected_cash,actual_cash,difference,shift_id,counted_at,count_json,variance_reason,approved_by,approval_note) "
                             "VALUES(date('now','localtime'),?,?,?,?,?,?,?,?,?,?,?)",
                             (summary["cashier"], summary["opening_cash"], summary["expected_cash"], actual, diff, int(shift_id),
                              validated["counted_at"], validated["count_json"], validated["variance_reason"], validated["approved_by"], str(approval_note or '').strip()))
            else:
                conn.execute("INSERT INTO cashup_records(cashup_date,cashier,opening_float,expected_cash,actual_cash,difference,shift_id) "
                             "VALUES(date('now','localtime'),?,?,?,?,?,?)",
                             (summary["cashier"], summary["opening_cash"], summary["expected_cash"], actual, diff, int(shift_id)))
        else:
            conn.execute("INSERT INTO cashup_records(cashup_date,cashier,opening_float,expected_cash,actual_cash,difference) "
                         "VALUES(date('now','localtime'),?,?,?,?,?)",
                         (summary["cashier"], summary["opening_cash"], summary["expected_cash"], actual, diff))
    summary.update({"actual_cash": round(actual,2), "difference": diff})
    return summary
