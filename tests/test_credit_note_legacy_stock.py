import os, sqlite3, tempfile, unittest

from services.stock_service import record_stock_movement


class TestCreditNoteLegacyStockMovement(unittest.TestCase):
    def test_credit_note_movement_populates_legacy_quantity_column(self):
        fd, path = tempfile.mkstemp(suffix=".db"); os.close(fd)
        try:
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE products(barcode TEXT PRIMARY KEY, description TEXT, soh REAL, cost_price REAL)")
            conn.execute("INSERT INTO products VALUES('ABC','Test Product',10,5)")
            conn.execute("""CREATE TABLE stock_movements(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                barcode TEXT,
                description TEXT,
                movement_type TEXT,
                qty REAL,
                quantity REAL NOT NULL,
                qty_before REAL,
                qty_after REAL,
                cost_price REAL,
                reference TEXT,
                reason TEXT,
                cashier TEXT)""")
            record_stock_movement('ABC','RETURN',2,'CREDIT NOTE #1','Test Product',10,12,5,'reason','cashier',conn)
            row=conn.execute("SELECT qty,quantity,qty_before,qty_after,movement_type,reference FROM stock_movements").fetchone()
            self.assertEqual(row,(2.0,2.0,10.0,12.0,'RETURN','CREDIT NOTE #1'))
            conn.close()
        finally:
            if os.path.exists(path): os.remove(path)

if __name__ == '__main__': unittest.main()
