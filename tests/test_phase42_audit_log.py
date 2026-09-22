import sqlite3
from core.audit_log import ensure_audit_table, record_event, recent_events

def test_audit_log_round_trip():
    conn = sqlite3.connect(":memory:")
    ensure_audit_table(conn)
    row_id = record_event(
        conn,
        "TEST",
        "Phase 42 audit test",
        username="tester",
        reference_type="test",
        reference_id=123,
        details={"ok": True},
    )
    assert row_id > 0
    rows = recent_events(conn, 10)
    assert rows
    # id, event_time, username, event_type, description, reference_type, reference_id, details_json
    assert rows[0][2] == "tester"
    assert rows[0][3] == "TEST"
    assert rows[0][5] == "test"
    assert rows[0][6] == "123"
