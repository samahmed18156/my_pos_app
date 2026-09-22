import sqlite3
from pathlib import Path
from services.recovery_hardening import full_database_health, restore_to_new_file, sqlite_diagnostics


def make_db(path: Path):
    c=sqlite3.connect(path)
    c.executescript('''
    CREATE TABLE products(barcode TEXT PRIMARY KEY, description TEXT NOT NULL, selling_price REAL NOT NULL, cost_price REAL, soh REAL);
    CREATE TABLE sales_history(id INTEGER PRIMARY KEY, total_amount REAL, total_cost REAL, payment_type TEXT);
    CREATE TABLE sale_items(id INTEGER PRIMARY KEY, sale_id INTEGER, barcode TEXT, qty REAL, price REAL, value REAL, cost_price REAL);
    CREATE TABLE stock_movements(id INTEGER PRIMARY KEY, barcode TEXT, movement_type TEXT, qty REAL, qty_before REAL, qty_after REAL);
    CREATE TABLE grn_headers(id INTEGER PRIMARY KEY, grn_no TEXT, supplier_id INTEGER, subtotal REAL, vat REAL, total REAL);
    CREATE TABLE grn_items(id INTEGER PRIMARY KEY, grn_id INTEGER, barcode TEXT, qty_received REAL, cost_price REAL, value REAL);
    CREATE TABLE users(id INTEGER PRIMARY KEY, username TEXT); CREATE TABLE branches(id INTEGER PRIMARY KEY, name TEXT);
    CREATE TABLE customers(id INTEGER PRIMARY KEY, name TEXT); CREATE TABLE account_transactions(id INTEGER PRIMARY KEY);
    ''')
    c.execute("INSERT INTO products VALUES ('A','Item',10,5,3)")
    c.commit(); c.close()


def test_good_database_health(tmp_path):
    p=tmp_path/'ok.db'; make_db(p); r=full_database_health(p); assert r['ok'], r


def test_missing_file_is_reported(tmp_path):
    r=full_database_health(tmp_path/'missing.db'); assert not r['ok']; assert 'database file missing' in r['problems']


def test_orphan_sale_is_reported(tmp_path):
    p=tmp_path/'bad.db'; make_db(p); c=sqlite3.connect(p); c.execute("INSERT INTO sale_items VALUES (1,999,'A',1,10,10,5)"); c.commit(); c.close()
    r=full_database_health(p); assert not r['ok']; assert r['readiness']['orphan_sale_items']==1


def test_restore_creates_valid_new_file_without_overwrite(tmp_path):
    src=tmp_path/'backup.db'; make_db(src); dest=tmp_path/'restored.db'
    r=restore_to_new_file(src,dest); assert r['ok']; assert dest.exists(); assert sqlite_diagnostics(dest)['integrity']
