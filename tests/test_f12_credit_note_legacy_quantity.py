import os, sqlite3, tempfile, unittest

from services.stock_service import record_stock_movement


class TestF12CreditNoteLegacyQuantity(unittest.TestCase):
    def test_canonical_ledger_with_legacy_not_null_quantity_accepts_f12_movement(self):
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        try:
            con = sqlite3.connect(path)
            con.execute('CREATE TABLE products(barcode TEXT PRIMARY KEY, description TEXT, soh REAL, cost_price REAL)')
            con.execute("INSERT INTO products VALUES ('A','Widget',5,10)")
            con.execute('''CREATE TABLE stock_movements(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                barcode TEXT,
                description TEXT,
                movement_type TEXT NOT NULL,
                qty REAL NOT NULL,
                quantity REAL NOT NULL,
                qty_before REAL,
                qty_after REAL,
                cost_price REAL DEFAULT 0,
                reference TEXT,
                reason TEXT,
                cashier TEXT DEFAULT 'Unknown')''')
            record_stock_movement('A', 'RETURN', 2, 'CREDIT NOTE #7', 'Widget', 5, 7, 10, 'F12', 'cashier', con)
            row = con.execute('SELECT qty, quantity, movement_type, reference FROM stock_movements').fetchone()
            self.assertEqual(row, (2.0, 2.0, 'RETURN', 'CREDIT NOTE #7'))
            con.close()
        finally:
            if os.path.exists(path): os.remove(path)


if __name__ == '__main__':
    unittest.main()
