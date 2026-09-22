import sqlite3
from core.audit_log import ensure_audit_table, record_event

def test_database_audit_table_creation():
    conn = sqlite3.connect(":memory:")
    ensure_audit_table(conn)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(audit_log)").fetchall()]
    assert "event_time" in cols
    assert "event_type" in cols
    assert "username" in cols

    row_id = record_event(conn, "TEST", "database integration")
    assert row_id > 0
    assert conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0] == 1
