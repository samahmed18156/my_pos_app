import sqlite3
import tempfile
import unittest
from pathlib import Path
from services.production_readiness import database_readiness, jasper_runtime_readiness


class ProductionReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _base(self):
        db = self.root / 'pos_store.db'
        c = sqlite3.connect(db)
        c.executescript('''
            CREATE TABLE users(id INTEGER PRIMARY KEY);
            CREATE TABLE products(barcode TEXT PRIMARY KEY, description TEXT, selling_price REAL, cost_price REAL, soh REAL);
            CREATE TABLE branches(id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE stock_movements(id INTEGER PRIMARY KEY, barcode TEXT, movement_type TEXT, qty REAL, qty_before REAL, qty_after REAL);
            CREATE TABLE sales_history(id INTEGER PRIMARY KEY, total_amount REAL, total_cost REAL, payment_type TEXT);
            CREATE TABLE sale_items(id INTEGER PRIMARY KEY, sale_id INTEGER, barcode TEXT, qty REAL, price REAL, value REAL, cost_price REAL);
            CREATE TABLE customers(id INTEGER PRIMARY KEY);
            CREATE TABLE account_transactions(id INTEGER PRIMARY KEY, account_id INTEGER, txn_type TEXT, total_amount REAL);
            CREATE TABLE grn_headers(id INTEGER PRIMARY KEY, grn_no TEXT, supplier_id INTEGER, subtotal REAL, vat REAL, total REAL);
            CREATE TABLE grn_items(id INTEGER PRIMARY KEY, grn_id INTEGER, barcode TEXT, qty_received REAL, cost_price REAL, value REAL);
            CREATE TABLE branch_stock(barcode TEXT, soh REAL);
            INSERT INTO products VALUES('A','Widget',100,10,5);
        ''')
        c.commit(); c.close()
        return db

    def test_clean_database_passes(self):
        result = database_readiness(self._base())
        self.assertTrue(result['ok'], result)

    def test_negative_stock_is_flagged(self):
        db = self._base(); c = sqlite3.connect(db); c.execute("UPDATE products SET soh=-1 WHERE barcode='A'"); c.commit(); c.close()
        result = database_readiness(db)
        self.assertFalse(result['ok']); self.assertEqual(result['negative_global_stock'], ['A'])

    def test_orphan_sale_line_is_flagged(self):
        db = self._base(); c = sqlite3.connect(db); c.execute("INSERT INTO sale_items VALUES(1,999,'A',1,100,100,10)"); c.commit(); c.close()
        result = database_readiness(db)
        self.assertFalse(result['ok']); self.assertEqual(result['orphan_sale_items'], 1)

    def test_orphan_grn_line_is_flagged(self):
        db = self._base(); c = sqlite3.connect(db); c.execute("INSERT INTO grn_items VALUES(1,999,'A',1,10,10)"); c.commit(); c.close()
        result = database_readiness(db)
        self.assertFalse(result['ok']); self.assertEqual(result['orphan_grn_items'], 1)

    def test_missing_cost_column_is_flagged(self):
        db = self._base(); c = sqlite3.connect(db); c.execute("CREATE TABLE sale_items_old(id INTEGER PRIMARY KEY, sale_id INTEGER, barcode TEXT, qty REAL, price REAL, value REAL)"); c.execute("DROP TABLE sale_items"); c.execute("ALTER TABLE sale_items_old RENAME TO sale_items"); c.commit(); c.close()
        result = database_readiness(db)
        self.assertFalse(result['ok']); self.assertIn('cost_price', result['missing_columns']['sale_items'])

    def test_missing_database_is_not_ready(self):
        result = database_readiness(self.root / 'missing.db')
        self.assertFalse(result['ok']); self.assertFalse(result['exists'])

    def test_jasper_runtime_check(self):
        runtime = self.root / 'jasper_runtime'; runtime.mkdir()
        (runtime / 'jasperreports-6.21.3.jar').write_bytes(b'x' * 1000001)
        (runtime / 'jasperreports-metadata-6.21.3.jar').write_bytes(b'x' * 1001)
        self.assertTrue(jasper_runtime_readiness(runtime)['ok'])


if __name__ == '__main__':
    unittest.main()
