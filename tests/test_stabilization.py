import os
import sqlite3
import tempfile
import unittest

import security
import services.stock_service as stock_service


class SecurityTests(unittest.TestCase):
    def test_password_hash_is_not_plaintext_and_verifies(self):
        password = "Correct-Horse-42!"
        encoded = security.hash_password(password)
        self.assertNotEqual(encoded, password)
        self.assertTrue(encoded.startswith("pbkdf2_sha256$"))
        self.assertTrue(security.verify_password(password, encoded))
        self.assertFalse(security.verify_password("wrong", encoded))


class StockServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.close()
        self.db_path = self.tmp.name
        self.old_path = stock_service.DB_PATH
        stock_service.DB_PATH = self.db_path
        c = sqlite3.connect(self.db_path)
        c.executescript("""
            CREATE TABLE products (
                barcode TEXT PRIMARY KEY,
                description TEXT,
                selling_price REAL,
                cost_price REAL,
                soh REAL
            );
            CREATE TABLE stock_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                barcode TEXT,
                description TEXT,
                movement_type TEXT,
                qty REAL,
                qty_before REAL,
                qty_after REAL,
                cost_price REAL,
                reference TEXT,
                reason TEXT,
                cashier TEXT
            );
            INSERT INTO products VALUES ('100', 'Test Item', 10, 6, 8);
        """)
        c.commit(); c.close()

    def tearDown(self):
        stock_service.DB_PATH = self.old_path
        os.unlink(self.db_path)

    def test_service_uses_current_schema(self):
        stock_service.record_stock_movement(
            '100', 'SALE', -2, reference='SALE #1',
            description='Test Item', qty_before=8, qty_after=6,
            cost_price=6, reason='Normal sale', cashier='tester'
        )
        c = sqlite3.connect(self.db_path)
        row = c.execute("SELECT barcode,movement_type,qty,qty_before,qty_after,reference FROM stock_movements").fetchone()
        c.close()
        self.assertEqual(row, ('100', 'SALE', -2.0, 8.0, 6.0, 'SALE #1'))

    def test_service_raises_for_unknown_product_when_deriving_state(self):
        with self.assertRaises(ValueError):
            stock_service.record_stock_movement('999', 'SALE', -1)


if __name__ == '__main__':
    unittest.main()
