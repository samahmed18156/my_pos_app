import sqlite3
import tempfile
from pathlib import Path
import unittest

class StockMovementSchemaMigrationTests(unittest.TestCase):
    def setUp(self):
        self.con = sqlite3.connect(":memory:")

    def tearDown(self):
        self.con.close()

    def test_new_movement_populates_legacy_quantity_column(self):
        from services.stock_service import record_stock_movement
        self.con.executescript("""
            CREATE TABLE products(barcode TEXT PRIMARY KEY, description TEXT, cost_price REAL, soh REAL);
            INSERT INTO products VALUES('100','Test',10,5);
            CREATE TABLE stock_movements(
                id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp DATETIME,
                product_id INTEGER, movement_type TEXT NOT NULL, quantity REAL NOT NULL,
                reference TEXT, created_at DATETIME
            );
            ALTER TABLE stock_movements ADD COLUMN barcode TEXT;
            ALTER TABLE stock_movements ADD COLUMN description TEXT;
            ALTER TABLE stock_movements ADD COLUMN qty REAL;
            ALTER TABLE stock_movements ADD COLUMN qty_before REAL;
            ALTER TABLE stock_movements ADD COLUMN qty_after REAL;
            ALTER TABLE stock_movements ADD COLUMN cost_price REAL DEFAULT 0;
            ALTER TABLE stock_movements ADD COLUMN reason TEXT;
            ALTER TABLE stock_movements ADD COLUMN cashier TEXT DEFAULT 'Unknown';
        """)
        record_stock_movement('100','GRN',3,reference='GRN-1',qty_before=5,qty_after=8,conn=self.con)
        self.assertEqual(self.con.execute('SELECT quantity,qty FROM stock_movements').fetchone(), (3.0,3.0))

    def test_legacy_stock_movements_gets_canonical_columns_and_index(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / 'legacy.db'
            con = sqlite3.connect(db)
            con.executescript('''
                CREATE TABLE products(
                    barcode TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    selling_price REAL NOT NULL,
                    cost_price REAL DEFAULT 0,
                    soh REAL DEFAULT 0
                );
                INSERT INTO products VALUES ('123','Test product',10,5,7);
                CREATE TABLE stock_movements(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER,
                    movement_type TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    reference TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                INSERT INTO stock_movements(product_id,movement_type,quantity,reference)
                VALUES (1,'GRN',5,'GRN-1');
            ''')
            con.commit(); con.close()

            import os, sys
            sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
            import database
            old_path = database.DB_PATH
            database.DB_PATH = str(db)
            try:
                database.init_db()
            finally:
                database.DB_PATH = old_path

            con = sqlite3.connect(db)
            cols = {r[1] for r in con.execute('PRAGMA table_info(stock_movements)')}
            self.assertTrue({'barcode','description','qty','timestamp','qty_before','qty_after','cost_price','reason','cashier'} <= cols)
            row = con.execute('SELECT barcode,description,qty,reference FROM stock_movements WHERE id=1').fetchone()
            self.assertEqual(row, ('123','Test product',5.0,'GRN-1'))
            self.assertIsNotNone(con.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_stock_movements_barcode_time'").fetchone())
            self.assertEqual(con.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            con.close()

if __name__ == '__main__':
    unittest.main()
