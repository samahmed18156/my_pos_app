from core.logger import logger as _bkpos_logger
import sqlite3
import os
import secrets
from pathlib import Path
from core.config import DB_PATH
from security import hash_password
from core.audit_log import ensure_audit_table

def _products_table_is_outdated(cursor):
    """Checks if an existing 'products' table is missing the columns
    the app now needs (e.g. it's a leftover table from an older version)."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='products'")
    if cursor.fetchone() is None:
        return False  # table doesn't exist yet - nothing to fix, will be created fresh

    cursor.execute("PRAGMA table_info(products)")
    existing_cols = [col[1] for col in cursor.fetchall()]
    required_cols = ["barcode", "description", "selling_price", "cost_price", "soh"]
    return not all(col in existing_cols for col in required_cols)


def _table_exists(cursor, table_name):
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None


def _add_column_if_missing(cursor, table_name, column_name, column_def):
    """Adds a column to an existing table if it isn't there yet, without
    touching any of the real data already in that table."""
    if not _table_exists(cursor, table_name):
        return  # table will be created fresh below, with the column included
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing_cols = [col[1] for col in cursor.fetchall()]
    if column_name not in existing_cols:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_def}")


def _upgrade_stock_movements_schema(cursor):
    """Upgrade the legacy stock movement ledger to the canonical schema.

    Older BKPOS databases used product_id/quantity/created_at.  Newer code
    uses barcode/qty/timestamp plus before/after quantities.  SQLite cannot
    change an existing table with CREATE TABLE IF NOT EXISTS, so we add the
    canonical columns in-place and backfill what can be recovered. Existing
    movement rows are preserved.
    """
    if not _table_exists(cursor, "stock_movements"):
        return

    for column, definition in (
        ("timestamp", "DATETIME"),
        ("barcode", "TEXT"),
        ("description", "TEXT"),
        ("qty", "REAL"),
        ("qty_before", "REAL"),
        ("qty_after", "REAL"),
        ("cost_price", "REAL DEFAULT 0.0"),
        ("reason", "TEXT"),
        ("cashier", "TEXT DEFAULT 'Unknown'"),
    ):
        _add_column_if_missing(cursor, "stock_movements", column, definition)

    cols = {r[1] for r in cursor.execute("PRAGMA table_info(stock_movements)").fetchall()}
    if "quantity" in cols:
        cursor.execute("UPDATE stock_movements SET qty=quantity WHERE qty IS NULL")
    if "created_at" in cols:
        cursor.execute("UPDATE stock_movements SET timestamp=created_at WHERE timestamp IS NULL")
    if "product_id" in cols:
        # product_id in the legacy ledger was the SQLite rowid of products.
        # Recover the barcode/description where possible without deleting data.
        cursor.execute("""
            UPDATE stock_movements
               SET barcode=(SELECT p.barcode FROM products p WHERE p.rowid=stock_movements.product_id),
                   description=(SELECT p.description FROM products p WHERE p.rowid=stock_movements.product_id)
             WHERE barcode IS NULL
        """)




def _upgrade_sales_schema(cursor):
    """Upgrade all columns used by the transactional sales service/UI."""
    sales_fields = (
        ("cashier", "TEXT DEFAULT 'Unknown'"),
        ("branch_id", "INTEGER DEFAULT 1"),
        ("branch_name", "TEXT DEFAULT 'Main Store'"),
        ("customer_id", "INTEGER"),
        ("customer_account", "TEXT"),
        ("customer_name", "TEXT"),
        ("amount_tendered", "REAL DEFAULT 0"),
        ("change_amount", "REAL DEFAULT 0"),
        ("cash_amount", "REAL DEFAULT 0"),
        ("card_amount", "REAL DEFAULT 0"),
        ("customer_type", "TEXT DEFAULT 'Retail'"),
        ("pricing_mode", "TEXT DEFAULT 'Retail'"),
        ("voided", "INTEGER DEFAULT 0"),
        ("status", "TEXT DEFAULT 'COMPLETED'"),
        ("below_cost_override", "INTEGER DEFAULT 0"),
        ("invoice_ref", "TEXT"),
        ("voided_at", "DATETIME"),
        ("voided_by", "TEXT DEFAULT ''"),
        ("sale_no", "TEXT"),
        ("transaction_uid", "TEXT"),
    )
    for column, definition in sales_fields:
        _add_column_if_missing(cursor, "sales_history", column, definition)
    _add_column_if_missing(cursor, "sale_items", "cost_price", "REAL DEFAULT 0")
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_sales_history_sale_no "
        "ON sales_history(sale_no) WHERE sale_no IS NOT NULL AND TRIM(sale_no) <> ''"
    )
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_sales_history_transaction_uid "
        "ON sales_history(transaction_uid) WHERE transaction_uid IS NOT NULL AND TRIM(transaction_uid) <> ''"
    )
    # Give legacy completed sales stable document numbers.
    cursor.execute(
        "UPDATE sales_history SET sale_no='INV-' || printf('%06d', id) "
        "WHERE sale_no IS NULL OR TRIM(sale_no)=''"
    )


def _upgrade_supplier_credit_schema(cursor):
    """Ensure supplier stock-credit tables support the current lifecycle API."""
    cursor.execute("""CREATE TABLE IF NOT EXISTS supplier_credits(
        id INTEGER PRIMARY KEY AUTOINCREMENT, credit_no TEXT UNIQUE NOT NULL,
        supplier_id INTEGER NOT NULL, credit_date TEXT NOT NULL, amount REAL NOT NULL CHECK(amount>0),
        reason TEXT, reference TEXT, created_by TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        stock_returned REAL DEFAULT 0, item_count INTEGER DEFAULT 0, transaction_uid TEXT)""")
    cursor.execute("""CREATE TABLE IF NOT EXISTS supplier_credit_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT, credit_id INTEGER NOT NULL,
        grn_id INTEGER, grn_item_id INTEGER, barcode TEXT NOT NULL, description TEXT,
        qty REAL NOT NULL, unit_cost REAL NOT NULL, value REAL NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
    _add_column_if_missing(cursor, "supplier_credits", "transaction_uid", "TEXT")
    cursor.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_supplier_credits_transaction_uid "
        "ON supplier_credits(transaction_uid) WHERE transaction_uid IS NOT NULL AND TRIM(transaction_uid) <> ''"
    )

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Phase 42: guarantee the audit trail exists on every database initialization.
    ensure_audit_table(conn)

    # Never drop an existing products table during startup. Older databases
    # are upgraded in-place below so existing stock/product data is preserved.

    # Create Products Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            barcode TEXT PRIMARY KEY,
            description TEXT NOT NULL,
            selling_price REAL NOT NULL,
            cost_price REAL DEFAULT 0.0,
            soh REAL DEFAULT 0.0,
            promo_price REAL DEFAULT 0.0,
            promo_active INTEGER DEFAULT 0
        )
    """)

    # Upgrade product columns in-place for older databases.
    for column, definition in (
        ("description", "TEXT DEFAULT ''"),
        ("selling_price", "REAL DEFAULT 0.0"),
        ("cost_price", "REAL DEFAULT 0.0"),
        ("soh", "REAL DEFAULT 0.0"),
        ("promo_price", "REAL DEFAULT 0.0"),
        ("promo_active", "INTEGER DEFAULT 0"),
    ):
        _add_column_if_missing(cursor, "products", column, definition)

    # ===== SUPPLIER LINK ON GRN HEADERS =====
    if _table_exists(cursor, "grn_headers"):
        _add_column_if_missing(cursor, "grn_headers", "supplier_id", "INTEGER")

    # ===== ADD BRANCH COLUMNS TO SALES_HISTORY =====
    _add_column_if_missing(cursor, "sales_history", "cashier", "TEXT DEFAULT 'Unknown'")
    _add_column_if_missing(cursor, "sales_history", "branch_id", "INTEGER DEFAULT 1")
    _add_column_if_missing(cursor, "sales_history", "branch_name", "TEXT DEFAULT 'Main Store'")
    _add_column_if_missing(cursor, "sales_history", "customer_id", "INTEGER")
    _add_column_if_missing(cursor, "sales_history", "customer_account", "TEXT")
    _add_column_if_missing(cursor, "sales_history", "customer_name", "TEXT")

    # Create Sales History Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            total_amount REAL,
            total_cost REAL,
            payment_type TEXT,
            cashier TEXT DEFAULT 'Unknown',
            branch_id INTEGER DEFAULT 1,
            branch_name TEXT DEFAULT 'Main Store',
            customer_id INTEGER,
            customer_account TEXT,
            customer_name TEXT,
            amount_tendered REAL DEFAULT 0,
            change_amount REAL DEFAULT 0,
            cash_amount REAL DEFAULT 0,
            card_amount REAL DEFAULT 0,
            customer_type TEXT DEFAULT 'Retail',
            pricing_mode TEXT DEFAULT 'Retail',
            voided INTEGER DEFAULT 0,
            status TEXT DEFAULT 'COMPLETED',
            below_cost_override INTEGER DEFAULT 0,
            invoice_ref TEXT,
            voided_at DATETIME,
            voided_by TEXT DEFAULT '',
            sale_no TEXT,
            transaction_uid TEXT
        )
    """)

    # Create Sale Items Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER,
            barcode TEXT,
            description TEXT,
            qty REAL,
            price REAL,
            value REAL,
            cost_price REAL DEFAULT 0
        )
    """)
    _upgrade_sales_schema(cursor)

    # Create canonical stock movement ledger used by the current services.
    # Existing legacy ledgers are upgraded in-place before the index is created.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            barcode TEXT,
            description TEXT,
            movement_type TEXT NOT NULL,
            qty REAL NOT NULL,
            qty_before REAL,
            qty_after REAL,
            cost_price REAL DEFAULT 0.0,
            reference TEXT,
            reason TEXT,
            cashier TEXT DEFAULT 'Unknown'
        )
    """)
    _upgrade_stock_movements_schema(cursor)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_stock_movements_barcode_time ON stock_movements(barcode, timestamp)")

    # ===== RETURNS / REFUNDS =====
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS return_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            original_sale_id INTEGER NOT NULL,
            total_amount REAL NOT NULL DEFAULT 0,
            refund_type TEXT NOT NULL,
            cashier TEXT DEFAULT 'Unknown',
            reason TEXT DEFAULT ''
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS return_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            return_id INTEGER NOT NULL,
            sale_item_id INTEGER NOT NULL,
            barcode TEXT,
            description TEXT,
            qty REAL NOT NULL,
            price REAL NOT NULL,
            value REAL NOT NULL
        )
    """)

    # ===== ADD BRANCH COLUMN TO USERS =====
    _add_column_if_missing(cursor, "users", "branch_id", "INTEGER DEFAULT 1")

    # Create Users Table. The legacy password column is retained only for
    # schema compatibility; active passwords live in password_hash.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL DEFAULT '',
            password_hash TEXT,
            full_name TEXT,
            role TEXT DEFAULT 'cashier',
            can_edit_price INTEGER DEFAULT 0,
            can_edit_qty INTEGER DEFAULT 1,
            can_delete_items INTEGER DEFAULT 1,
            can_view_reports INTEGER DEFAULT 1,
            can_access_stock INTEGER DEFAULT 0,
            can_access_debtors INTEGER DEFAULT 0,
            can_access_creditors INTEGER DEFAULT 0,
            can_access_utility INTEGER DEFAULT 0,
            branch_id INTEGER DEFAULT 1
        )
    """)

    # Production authorization columns. Existing users keep their current permissions.
    _add_column_if_missing(cursor, "users", "must_change_password", "INTEGER NOT NULL DEFAULT 0")
    for _perm in ("can_void_sales", "can_issue_credit_notes", "can_manage_users", "can_manage_branches", "can_cashup", "can_manage_expenses"):
        _add_column_if_missing(cursor, "users", _perm, "INTEGER NOT NULL DEFAULT 0")

    # Upgrade legacy users table and migrate any existing plaintext passwords
    # exactly once. After migration, the legacy column is blank.
    _add_column_if_missing(cursor, "users", "password_hash", "TEXT")
    cursor.execute("SELECT id, password, password_hash FROM users")
    for uid, legacy_password, password_hash_value in cursor.fetchall():
        if (not password_hash_value) and legacy_password:
            cursor.execute("UPDATE users SET password_hash=?, password='' WHERE id=?",
                           (hash_password(str(legacy_password)), uid))

    # Seed the first Admin account with a random one-time password.
    # A caller may provide BKPOS_INITIAL_ADMIN_PASSWORD for automated deployments.
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        initial_password = os.environ.get("BKPOS_INITIAL_ADMIN_PASSWORD", "").strip()
        generated = False
        if not initial_password:
            initial_password = secrets.token_urlsafe(18)
            generated = True
        cursor.execute("""
            INSERT INTO users (username, password, password_hash, full_name, role, must_change_password)
            VALUES ('admin', '', ?, 'Administrator', 'Admin', 1)
        """, (hash_password(initial_password),))
        if generated:
            credential_path = Path(DB_PATH).resolve().parent / ".bkpos_initial_admin_password"
            try:
                credential_path.write_text(initial_password + "\n", encoding="utf-8")
                try:
                    credential_path.chmod(0o600)
                except OSError:
                    _bkpos_logger.warning("Suppressed exception in database.py", exc_info=exc)
            except OSError:
                _bkpos_logger.warning("Suppressed exception in database.py", exc_info=exc)

    # Do not re-enable the first-run password prompt on every application start.
    # New installations seed the admin with must_change_password=1; once the
    # password is changed, that flag remains 0 until an administrator explicitly
    # resets it through an account-management workflow.
    cursor.execute("UPDATE users SET can_void_sales=1, can_issue_credit_notes=1, can_manage_users=1, can_manage_branches=1, can_cashup=1, can_manage_expenses=1 WHERE lower(role)='admin'")

    # Create Expenses Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT,
            amount REAL,
            date_logged DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create Accounts Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT,
            phone TEXT,
            address TEXT
        )
    """)

    # Supplier payment ledger
    cursor.execute("""CREATE TABLE IF NOT EXISTS supplier_payments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,supplier_id INTEGER NOT NULL,
        supplier_account_no TEXT,supplier_name TEXT NOT NULL,
        payment_date DATETIME DEFAULT CURRENT_TIMESTAMP,amount REAL NOT NULL,
        payment_method TEXT NOT NULL DEFAULT 'Bank Transfer',reference TEXT,
        notes TEXT,cashier TEXT DEFAULT 'Unknown')""")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_supplier_payments_supplier ON supplier_payments(supplier_id)")
    _upgrade_supplier_credit_schema(cursor)

    # Create Account Transactions Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS account_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER,
            txn_type TEXT,
            total_amount REAL,
            txn_date DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create Invoice Items Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoice_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            txn_id INTEGER,
            item_name TEXT,
            qty REAL,
            unit_price REAL
        )
    """)

    # ===== BRANCHES TABLE =====
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS branches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT,
            phone TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ===== ADD DEFAULT BRANCHES =====
    cursor.execute("SELECT COUNT(*) FROM branches")
    if cursor.fetchone()[0] == 0:
        default_branches = [
            ("Main Store", "123 Main Street, City", "+27 12 345 6789"),
            ("Branch 2", "456 Second Avenue, City", "+27 12 345 6780"),
            ("Branch 3", "789 Third Road, Town", "+27 12 345 6781"),
        ]
        cursor.executemany("""
            INSERT INTO branches (name, address, phone)
            VALUES (?, ?, ?)
        """, default_branches)

    # Seed products
    cursor.execute("SELECT COUNT(*) FROM products")
    if cursor.fetchone()[0] == 0:
        sample_products = [
            ("6009612470533", "AQUELLE FLAVOUR WATER 1.5L", 14.99, 10.00, 5.0),
            ("6009612470168", "AQUELLE FLAVOUR WATER 500ML", 9.99, 6.50, 2.0),
            ("6009612470595", "AQUELLE FLAVOUR WATER 6x1.5L", 87.99, 65.00, 27.0),
            ("6009612470304", "AQUELLE FLAVOUR WATER 6x500ML", 42.99, 30.00, 143.0),
            ("8790469", "AQUELLE SPARKLING WATER 6x1.5ML", 67.99, 45.00, 18.0),
            ("6009612470359", "AQUELLE SPARKLING WATER 6x500ML", 37.99, 25.00, 7.0),
            ("6009612470687", "AQUELLE STILL WATER 4x5L", 87.99, 60.00, 52.0),
            ("6009612470045", "AQUELLE STILL WATER 500ML", 7.99, 4.50, 0.0),
            ("6009612470649", "AQUELLE STILL WATER 5L", 24.99, 16.00, 2.0),
            ("6009612470342", "AQUELLE STILL WATER 6x500ML", 35.99, 24.00, 13.0),
            ("6009612470403", "AQUELLE STILLE WATER 6 X 1.5L", 67.99, 45.00, 30.0)
        ]
        cursor.executemany("""
            INSERT INTO products (barcode, description, selling_price, cost_price, soh)
            VALUES (?, ?, ?, ?, ?)
        """, sample_products)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()