import sqlite3
from audit_log import ensure_schema, log_action


def test_audit_log_records_sensitive_action(tmp_path, monkeypatch):
    db=tmp_path/'audit.db'
    import audit_log
    monkeypatch.setattr(audit_log,'DB_NAME',str(db))
    ensure_schema()
    log_action('manager','VOID','SALE','123','test reason','manager',2)
    c=sqlite3.connect(db)
    row=c.execute('SELECT username,action,entity_type,entity_id,details,branch_id FROM audit_log').fetchone(); c.close()
    assert row==('manager','VOID','SALE','123','test reason',2)


def test_audit_log_is_append_only(tmp_path, monkeypatch):
    db=tmp_path/'audit2.db'
    import audit_log
    monkeypatch.setattr(audit_log,'DB_NAME',str(db))
    ensure_schema(); log_action('admin','TEST','X','1','immutable','Admin',1)
    c=sqlite3.connect(db)
    import pytest
    with pytest.raises(sqlite3.DatabaseError): c.execute("UPDATE audit_log SET details='changed' WHERE id=1")
    with pytest.raises(sqlite3.DatabaseError): c.execute("DELETE FROM audit_log WHERE id=1")
    c.close()
