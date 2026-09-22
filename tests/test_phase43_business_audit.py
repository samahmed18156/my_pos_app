import sqlite3
from core.audit_log import ensure_audit_table, record_business_event

def test_business_event_round_trip():
    conn = sqlite3.connect(":memory:")
    ensure_audit_table(conn)
    row_id = record_business_event(
        conn,
        "INVOICE_CREATED",
        username="cashier",
        reference_type="invoice",
        reference_id=2088,
        description="Invoice created",
        details={"total": "125.00"},
    )
    row = conn.execute(
        "SELECT event_type, username, reference_type, reference_id, description "
        "FROM audit_log WHERE id=?", (row_id,)
    ).fetchone()
    assert row == (
        "INVOICE_CREATED", "cashier", "invoice", "2088", "Invoice created"
    )
