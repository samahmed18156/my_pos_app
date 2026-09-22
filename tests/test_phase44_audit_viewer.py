import sqlite3
from core.audit_log import ensure_audit_table, record_event
from core.audit_viewer import query_events, event_types

def test_audit_viewer_filters():
    conn = sqlite3.connect(":memory:")
    ensure_audit_table(conn)
    record_event(conn, "INVOICE_CREATED", "Invoice created",
                 username="admin", reference_type="invoice", reference_id=100)
    record_event(conn, "GRN_CREATED", "GRN created",
                 username="cashier", reference_type="grn", reference_id=55)

    rows = query_events(conn, username="admin", event_type="INVOICE_CREATED")
    assert len(rows) == 1
    assert rows[0][2] == "admin"
    assert rows[0][3] == "INVOICE_CREATED"
    assert rows[0][6] == "100"
    assert "INVOICE_CREATED" in event_types()
