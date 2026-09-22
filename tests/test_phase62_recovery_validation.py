import sqlite3
from pathlib import Path

from services.recovery_validation import validate_backup_roundtrip, validate_restore_roundtrip
from services.recovery_hardening import restore_to_new_file


def make_db(path: Path):
    c = sqlite3.connect(path)
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
    c.execute("INSERT INTO sales_history VALUES (1,10,5,'CASH')")
    c.commit(); c.close()


def test_backup_roundtrip_is_verified(tmp_path):
    p = tmp_path / 'live.db'; make_db(p)
    r = validate_backup_roundtrip(p)
    assert r['ok'], r
    assert r['backup']['sqlite']['quick_check'] == 'ok'


def test_restore_roundtrip_is_verified(tmp_path):
    p = tmp_path / 'backup.db'; make_db(p)
    r = validate_restore_roundtrip(p)
    assert r['ok'], r
    assert r['restored']['sqlite']['quick_check'] == 'ok'


def test_corrupt_backup_is_rejected(tmp_path):
    p = tmp_path / 'bad.db'
    p.write_bytes(b'not a sqlite database')
    r = validate_restore_roundtrip(p)
    assert not r['ok']
    assert r['stage'] == 'source'


def test_restore_never_overwrites_existing_destination(tmp_path):
    src = tmp_path / 'backup.db'; make_db(src)
    dest = tmp_path / 'existing.db'; make_db(dest)
    try:
        restore_to_new_file(src, dest)
    except FileExistsError:
        pass
    else:
        raise AssertionError('restore_to_new_file overwrote an existing destination')
