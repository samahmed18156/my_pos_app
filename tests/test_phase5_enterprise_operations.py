import os
import sqlite3
import tempfile
from enterprise_operations import database_snapshot, backup_snapshot, audit_snapshot, operational_exceptions
from services.production_hardening import backup_database


def make_db(path):
    c = sqlite3.connect(path)
    c.executescript('''
      CREATE TABLE products(barcode TEXT, description TEXT, soh REAL DEFAULT 0);
      CREATE TABLE sales_history(id INTEGER PRIMARY KEY, total_amount REAL DEFAULT 0);
      CREATE TABLE users(id INTEGER PRIMARY KEY, active INTEGER DEFAULT 1);
      CREATE TABLE branches(id INTEGER PRIMARY KEY, name TEXT);
      CREATE TABLE sale_items(id INTEGER PRIMARY KEY, sale_id INTEGER);
      CREATE TABLE audit_log(id INTEGER PRIMARY KEY, timestamp TEXT, action TEXT);
      INSERT INTO products VALUES ('1','Test',5);
      INSERT INTO sales_history VALUES (1,100);
      INSERT INTO users VALUES (1,1);
      INSERT INTO branches VALUES (1,'Main');
      INSERT INTO audit_log VALUES (1,date('now'),'VOID_SALE');
      INSERT INTO audit_log VALUES (2,date('now'),'STOCK_TRANSFER');
    ''')
    c.commit(); c.close()


def test_database_snapshot_reports_core_metrics():
    with tempfile.TemporaryDirectory() as d:
        p=os.path.join(d,'pos.db'); make_db(p)
        snap=database_snapshot(p)
        assert snap['exists'] and snap['integrity']
        assert snap['sales']==1 and snap['users']==1 and snap['branches']==1
        assert snap['tables']>=5


def test_backup_snapshot_verifies_recent_backups():
    with tempfile.TemporaryDirectory() as d:
        src=os.path.join(d,'src.db'); make_db(src)
        backup_dir=os.path.join(d,'backups'); os.mkdir(backup_dir)
        target=os.path.join(backup_dir,'backup.db'); backup_database(src,target)
        snap=backup_snapshot(backup_dir)
        assert snap['count']==1 and snap['verified']==1 and snap['newest']


def test_audit_snapshot_counts_sensitive_actions():
    with tempfile.TemporaryDirectory() as d:
        p=os.path.join(d,'pos.db'); make_db(p)
        snap=audit_snapshot(p)
        assert snap['log_available']
        assert snap['events']==2 and snap['voids']==1 and snap['transfers']==1


def test_operational_exceptions_flags_negative_stock_and_orphans():
    with tempfile.TemporaryDirectory() as d:
        p=os.path.join(d,'pos.db'); make_db(p)
        c=sqlite3.connect(p)
        c.execute("UPDATE products SET soh=-2")
        c.execute("INSERT INTO sale_items(id,sale_id) VALUES(1,999)")
        c.commit(); c.close()
        issues=operational_exceptions(p)
        assert any('negative stock' in x for x in issues)
        assert any('orphan sale-item' in x for x in issues)
