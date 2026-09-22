import sqlite3, tempfile, unittest
from pathlib import Path
from services.production_health import check_database, check_required_tables, run_health_check

class Phase50ProductionHealthTests(unittest.TestCase):
    def make_db(self):
        fd,name=tempfile.mkstemp(suffix='.db'); Path(name).unlink(); conn=sqlite3.connect(name); conn.execute('PRAGMA foreign_keys=ON'); return conn,name
    def test_healthy_database(self):
        conn,name=self.make_db()
        try:
            for table in ('products','sales_history','sale_items','stock_movements','grns','grn_items'): conn.execute(f'CREATE TABLE {table} (id INTEGER PRIMARY KEY)')
            conn.commit(); self.assertEqual(check_database(conn)[0],'OK'); self.assertEqual(check_required_tables(conn)[0],'OK')
            report=run_health_check(conn,name); self.assertEqual(report['overall'],'OK'); self.assertTrue(report['read_only'])
        finally: conn.close(); Path(name).unlink(missing_ok=True)
    def test_missing_required_table_is_reported(self):
        conn,name=self.make_db()
        try:
            conn.execute('CREATE TABLE products (id INTEGER PRIMARY KEY)'); status,_,details=check_required_tables(conn); self.assertEqual(status,'ERROR'); self.assertIn('sales_history',details['missing'])
        finally: conn.close(); Path(name).unlink(missing_ok=True)
    def test_corrupt_database_is_not_reported_as_healthy(self):
        conn,name=self.make_db(); conn.execute('CREATE TABLE products (id INTEGER PRIMARY KEY)'); conn.commit(); conn.close()
        Path(name).write_bytes(b'not a sqlite database'); conn=sqlite3.connect(name)
        try: self.assertEqual(check_database(conn)[0],'ERROR')
        finally: conn.close(); Path(name).unlink(missing_ok=True)
