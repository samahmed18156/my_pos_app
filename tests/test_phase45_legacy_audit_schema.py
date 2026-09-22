import sqlite3
from core.audit_log import ensure_audit_table, record_event

def test_legacy_audit_table_is_upgraded():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT)")
    conn.commit()
    ensure_audit_table(conn)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(audit_log)").fetchall()}
    assert "event_time" in cols
    assert "event_type" in cols
    row_id = record_event(conn, "LOGIN_FAILED", "legacy schema test", username="admin")
    assert row_id > 0
