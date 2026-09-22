"""BKPOS Phase 44 — Audit History query/report helpers."""

from __future__ import annotations

from typing import Optional

EVENT_TYPES = (
    "SALE_CREATED", "INVOICE_CREATED", "CREDIT_NOTE_CREATED",
    "DEBTOR_PAYMENT_RECEIVED", "CREDITOR_PAYMENT_MADE", "GRN_CREATED",
    "STOCK_ADJUSTMENT", "RETURN_PROCESSED", "DOCUMENT_REPRINTED",
    "PRODUCT_CHANGED", "PRICE_CHANGED", "BACKUP_CREATED",
    "BACKUP_RESTORED", "LOGIN_SUCCESS", "LOGIN_FAILED", "LOGOUT",
)

def query_events(
    conn,
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    username: Optional[str] = None,
    event_type: Optional[str] = None,
    reference_type: Optional[str] = None,
    reference_id: Optional[str] = None,
    limit: int = 500,
):
    """Return filtered audit events, newest first."""
    from .audit_log import ensure_audit_table
    ensure_audit_table(conn)
    limit = max(1, min(int(limit), 5000))
    clauses, params = [], []

    if start_date:
        clauses.append("event_time >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("event_time <= ?")
        params.append(end_date)
    if username:
        clauses.append("username = ?")
        params.append(username)
    if event_type:
        clauses.append("event_type = ?")
        params.append(event_type)
    if reference_type:
        clauses.append("reference_type = ?")
        params.append(reference_type)
    if reference_id:
        clauses.append("reference_id = ?")
        params.append(str(reference_id))

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return conn.execute(
        """SELECT id, event_time, username, event_type, description,
                  reference_type, reference_id, details_json
           FROM audit_log""" + where + " ORDER BY id DESC LIMIT ?",
        params + [limit],
    ).fetchall()

def event_types():
    return EVENT_TYPES
