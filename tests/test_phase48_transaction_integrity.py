import sqlite3
import pytest

from core.audit_log import ensure_audit_table, record_event, recent_events
from core.schema_manager import migrate_connection
from services.transaction_guard import transaction
from services.transaction_integrity import (
    assert_sale_integrity, assert_grn_integrity,
    assert_customer_invoice_integrity, assert_supplier_grn_integrity,
    assert_stock_movement_integrity,
)


def test_audit_event_rolls_back_with_business_transaction():
    c = sqlite3.connect(":memory:")
    ensure_audit_table(c)
    with pytest.raises(RuntimeError):
        with transaction(c):
            record_event(c, "SALE", "inside business transaction")
            raise RuntimeError("failure")
    assert recent_events(c, 10) == []


def test_standalone_audit_event_is_durable():
    c = sqlite3.connect(":memory:")
    event_id = record_event(c, "TEST", "standalone")
    assert event_id > 0
    assert recent_events(c, 10)[0][3] == "TEST"


def test_nested_transaction_uses_savepoint():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, value TEXT)")
    with transaction(c):
        c.execute("INSERT INTO t(value) VALUES('outer')")
        with pytest.raises(ValueError):
            with transaction(c):
                c.execute("INSERT INTO t(value) VALUES('inner')")
                raise ValueError("inner failure")
        c.execute("INSERT INTO t(value) VALUES('outer-2')")
    assert [r[0] for r in c.execute("SELECT value FROM t ORDER BY id")] == ["outer", "outer-2"]


def test_schema_migration_does_not_commit_outer_transaction():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE marker(value TEXT)")
    c.execute("BEGIN")
    c.execute("INSERT INTO marker VALUES('uncommitted')")
    migrate_connection(c)
    c.rollback()
    assert c.execute("SELECT COUNT(*) FROM marker").fetchone()[0] == 0
    assert c.execute("PRAGMA user_version").fetchone()[0] == 0


def test_sale_invariant():
    c = sqlite3.connect(":memory:")
    c.executescript("""
    CREATE TABLE sales_history(id INTEGER PRIMARY KEY,total_amount REAL,total_cost REAL);
    CREATE TABLE sale_items(id INTEGER PRIMARY KEY,sale_id INTEGER,value REAL,qty REAL,cost_price REAL);
    INSERT INTO sales_history VALUES(1,115,50);
    INSERT INTO sale_items VALUES(1,1,100,2,20);
    INSERT INTO sale_items VALUES(2,1,15,1,10);
    """)
    assert_sale_integrity(c, 1)


def test_grn_invoice_and_stock_invariants():
    c = sqlite3.connect(":memory:")
    c.executescript("""
    CREATE TABLE grn_headers(id INTEGER PRIMARY KEY,subtotal REAL,vat REAL,total REAL,paid REAL,outstanding REAL,status TEXT);
    CREATE TABLE grn_items(id INTEGER PRIMARY KEY,grn_id INTEGER,value REAL);
    CREATE TABLE customer_account_invoices(id INTEGER PRIMARY KEY,total REAL,paid REAL,outstanding REAL,status TEXT);
    CREATE TABLE stock_movements(id INTEGER PRIMARY KEY,qty_before REAL,qty_after REAL,qty REAL);
    INSERT INTO grn_headers VALUES(1,100,15,115,40,75,'PART PAID');
    INSERT INTO grn_items VALUES(1,1,115);
    INSERT INTO customer_account_invoices VALUES(1,200,50,150,'PART PAID');
    INSERT INTO stock_movements VALUES(1,10,7,-3);
    """)
    assert_grn_integrity(c, 1)
    assert_supplier_grn_integrity(c, 1)
    assert_customer_invoice_integrity(c, 1)
    assert_stock_movement_integrity(c, 1)
