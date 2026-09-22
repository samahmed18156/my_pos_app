import sqlite3
from core.schema_manager import migrate_connection, get_schema_version, SCHEMA_VERSION

def test_fresh_database():
    c=sqlite3.connect(":memory:")
    assert migrate_connection(c)==SCHEMA_VERSION
    assert get_schema_version(c)==SCHEMA_VERSION
    assert c.execute("SELECT name FROM sqlite_master WHERE name='audit_log'").fetchone()

def test_legacy_audit_database():
    c=sqlite3.connect(":memory:")
    c.execute("CREATE TABLE audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT)")
    assert migrate_connection(c)==SCHEMA_VERSION
    cols={r[1] for r in c.execute("PRAGMA table_info(audit_log)")}
    assert {"event_time","event_type","details_json"} <= cols

def test_legacy_stock_database():
    c=sqlite3.connect(":memory:")
    c.execute("""CREATE TABLE stock_movements(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER, movement_type TEXT NOT NULL,
        quantity REAL, reference TEXT, created_at TIMESTAMP)""")
    c.execute("INSERT INTO stock_movements(movement_type,quantity) VALUES('SALE',3)")
    assert migrate_connection(c)==SCHEMA_VERSION
    row=c.execute("SELECT qty,timestamp FROM stock_movements").fetchone()
    assert row[0]==3

def test_idempotent_repeat():
    c=sqlite3.connect(":memory:")
    assert migrate_connection(c)==SCHEMA_VERSION
    assert migrate_connection(c)==SCHEMA_VERSION

def test_newer_schema_rejected():
    c=sqlite3.connect(":memory:")
    c.execute("PRAGMA user_version=999")
    try:
        migrate_connection(c)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Newer database schema must not be downgraded")
