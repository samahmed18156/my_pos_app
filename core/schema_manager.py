"""BKPOS Phase 47 — safe database schema migration manager.

Migrations are deliberately additive and idempotent. Existing business data is
never dropped or replaced. The manager can be called repeatedly without
reapplying a migration.
"""
from __future__ import annotations

import sqlite3
from typing import Callable

SCHEMA_VERSION = 5

def _columns(conn, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}

def _table_exists(conn, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None

def _migration_1(conn):
    """Ensure the audit table has the current additive columns."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_time TEXT,
            username TEXT,
            event_type TEXT,
            description TEXT,
            reference_type TEXT,
            reference_id TEXT,
            details_json TEXT
        )
    """)
    cols=_columns(conn,"audit_log")
    additions={
        "event_time":"TEXT","username":"TEXT","event_type":"TEXT",
        "description":"TEXT","reference_type":"TEXT",
        "reference_id":"TEXT","details_json":"TEXT",
        "timestamp":"TEXT","role":"TEXT","action":"TEXT",
        "entity_type":"TEXT","entity_id":"TEXT","details":"TEXT",
        "branch_id":"INTEGER DEFAULT 1","reference":"TEXT",
    }
    for col,definition in additions.items():
        if col not in cols:
            conn.execute(f"ALTER TABLE audit_log ADD COLUMN {col} {definition}")
    conn.execute(
        "UPDATE audit_log SET event_time=CURRENT_TIMESTAMP "
        "WHERE event_time IS NULL"
    )
    conn.execute(
        "UPDATE audit_log SET event_type='LEGACY' "
        "WHERE event_type IS NULL"
    )

def _migration_2(conn):
    """Ensure stock movement compatibility columns exist on legacy ledgers."""
    if not _table_exists(conn,"stock_movements"):
        return
    cols=_columns(conn,"stock_movements")
    additions={
        "timestamp":"DATETIME",
        "barcode":"TEXT",
        "description":"TEXT",
        "qty":"REAL",
        "qty_before":"REAL",
        "qty_after":"REAL",
        "cost_price":"REAL DEFAULT 0.0",
        "reason":"TEXT",
        "cashier":"TEXT",
    }
    for col,definition in additions.items():
        if col not in cols:
            conn.execute(f"ALTER TABLE stock_movements ADD COLUMN {col} {definition}")
    cols=_columns(conn,"stock_movements")
    if "quantity" in cols and "qty" in cols:
        conn.execute("UPDATE stock_movements SET qty=quantity WHERE qty IS NULL")
    if "created_at" in cols and "timestamp" in cols:
        conn.execute(
            "UPDATE stock_movements SET timestamp=created_at "
            "WHERE timestamp IS NULL"
        )


def _migration_3(conn):
    """Add indexes for the highest-frequency lookup, history and account queries."""
    index_specs = {
        "products": [("idx_products_barcode", ["barcode"])],
        "sales_history": [("idx_sales_history_timestamp", ["timestamp"])],
        "sale_items": [("idx_sale_items_sale_id", ["sale_id"])],
        "grn_headers": [
            ("idx_grn_headers_supplier_id", ["supplier_id"]),
            ("idx_grn_headers_supplier_account", ["supplier_account"]),
        ],
        "grn_items": [("idx_grn_items_grn_id", ["grn_id"])],
        "stock_movements": [("idx_stock_movements_barcode_time", ["barcode", "timestamp"])],
        "branch_stock": [("idx_branch_stock_branch_barcode", ["branch_id", "barcode"])],
        "customer_account_transactions": [("idx_customer_account_tx_customer", ["customer_id"])],
        "customer_account_invoices": [("idx_customer_account_invoice_customer", ["customer_id"])],
        "supplier_payments": [("idx_supplier_payments_supplier", ["supplier_id"])],
        "supplier_credits": [("idx_supplier_credits_supplier", ["supplier_id"])],
        "account_transactions": [("idx_account_transactions_account_type", ["account_id", "txn_type"])],
        "audit_log": [
            ("idx_audit_log_event_time", ["event_time"]),
            ("idx_audit_log_event_type", ["event_type"]),
        ],
        "management_alerts": [("idx_management_alerts_status", ["status"])],
        "cashier_shifts": [("idx_cashier_shifts_status", ["status"])],
        "cashup_records": [("idx_cashup_records_date", ["cashup_date"])],
        "return_history": [("idx_return_history_timestamp", ["timestamp"])],
        "return_items": [("idx_return_items_return_id", ["return_id"])],
        "loyalty_transactions": [
            ("idx_loyalty_transactions_customer", ["customer_id"]),
            ("idx_loyalty_transactions_sale", ["sale_id"]),
        ],
    }
    for table, specs in index_specs.items():
        if not _table_exists(conn, table):
            continue
        cols = _columns(conn, table)
        for index_name, columns in specs:
            if all(col in cols for col in columns):
                quoted = ", ".join('"' + col.replace('"', '""') + '"' for col in columns)
                conn.execute(f'CREATE INDEX IF NOT EXISTS "{index_name}" ON "{table}" ({quoted})')


def _migration_4(conn):
    """Add stable document numbers and idempotency keys for core transactions."""
    specs = {
        "sales_history": [("sale_no", "TEXT"), ("transaction_uid", "TEXT")],
        "grn_headers": [("transaction_uid", "TEXT")],
        "return_history": [("return_no", "TEXT"), ("transaction_uid", "TEXT")],
        "supplier_credits": [("transaction_uid", "TEXT")],
    }
    for table, additions in specs.items():
        if not _table_exists(conn, table):
            continue
        cols = _columns(conn, table)
        for col, definition in additions:
            if col not in cols:
                conn.execute(f'ALTER TABLE {table} ADD COLUMN {col} {definition}')
    if _table_exists(conn, "sales_history"):
        conn.execute("UPDATE sales_history SET sale_no='INV-' || printf('%06d', id) WHERE sale_no IS NULL OR TRIM(sale_no)=''" )
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_sales_history_sale_no ON sales_history(sale_no)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_sales_history_transaction_uid ON sales_history(transaction_uid) WHERE transaction_uid IS NOT NULL AND TRIM(transaction_uid) <> ''")
    if _table_exists(conn, "grn_headers"):
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_grn_headers_transaction_uid ON grn_headers(transaction_uid) WHERE transaction_uid IS NOT NULL AND TRIM(transaction_uid) <> ''")
    if _table_exists(conn, "return_history"):
        conn.execute("UPDATE return_history SET return_no='CN-' || printf('%06d', id) WHERE return_no IS NULL OR TRIM(return_no)=''" )
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_return_history_return_no ON return_history(return_no)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_return_history_transaction_uid ON return_history(transaction_uid) WHERE transaction_uid IS NOT NULL AND TRIM(transaction_uid) <> ''")
    if _table_exists(conn, "supplier_credits"):
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_supplier_credits_transaction_uid ON supplier_credits(transaction_uid) WHERE transaction_uid IS NOT NULL AND TRIM(transaction_uid) <> ''")

def _migration_5(conn):
    """Add purchase-order lifecycle tables; POs never post stock or supplier liability."""
    conn.execute("""CREATE TABLE IF NOT EXISTS purchase_orders(
        id INTEGER PRIMARY KEY AUTOINCREMENT, po_no TEXT UNIQUE NOT NULL, supplier_id INTEGER NOT NULL,
        supplier_account TEXT, supplier_name TEXT NOT NULL, order_date TEXT NOT NULL, expected_date TEXT,
        notes TEXT, status TEXT NOT NULL DEFAULT 'DRAFT', total REAL NOT NULL DEFAULT 0,
        created_by TEXT DEFAULT 'Unknown', created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS purchase_order_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT, po_id INTEGER NOT NULL, barcode TEXT NOT NULL, description TEXT,
        ordered_qty REAL NOT NULL, unit_cost REAL NOT NULL, received_qty REAL NOT NULL DEFAULT 0, value REAL NOT NULL DEFAULT 0)""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_po_supplier ON purchase_orders(supplier_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_po_status ON purchase_orders(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_po_items_po ON purchase_order_items(po_id)")
    if _table_exists(conn,'grn_headers') and 'po_no' not in _columns(conn,'grn_headers'):
        conn.execute("ALTER TABLE grn_headers ADD COLUMN po_no TEXT")


MIGRATIONS: dict[int, Callable] = {
    1: _migration_1,
    2: _migration_2,
    3: _migration_3,
    4: _migration_4,
    5: _migration_5,
}

def get_schema_version(conn) -> int:
    return int(conn.execute("PRAGMA user_version").fetchone()[0])

def set_schema_version(conn, version: int) -> None:
    conn.execute(f"PRAGMA user_version={int(version)}")

def migrate_connection(conn) -> int:
    """Apply pending additive migrations without committing outer work."""
    owns_transaction = not conn.in_transaction
    current=get_schema_version(conn)
    if current > SCHEMA_VERSION:
        raise RuntimeError(
            f"Database schema version {current} is newer than this BKPOS "
            f"version {SCHEMA_VERSION}."
        )
    for version in range(current+1, SCHEMA_VERSION+1):
        MIGRATIONS[version](conn)
        set_schema_version(conn,version)
        if owns_transaction:
            conn.commit()
    return get_schema_version(conn)

def migrate_database(path: str) -> int:
    conn=sqlite3.connect(path)
    try:
        return migrate_connection(conn)
    finally:
        conn.close()
