import sqlite3
import unittest

from core.schema_manager import migrate_connection
from services.index_optimization import index_health


class Phase54IndexOptimizationTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.executescript("""
            CREATE TABLE products(id INTEGER PRIMARY KEY, barcode TEXT);
            CREATE TABLE sales_history(id INTEGER PRIMARY KEY, timestamp TEXT);
            CREATE TABLE sale_items(id INTEGER PRIMARY KEY, sale_id INTEGER);
            CREATE TABLE grn_headers(id INTEGER PRIMARY KEY, supplier_id INTEGER, supplier_account TEXT);
            CREATE TABLE grn_items(id INTEGER PRIMARY KEY, grn_id INTEGER);
            CREATE TABLE stock_movements(id INTEGER PRIMARY KEY, barcode TEXT, timestamp TEXT);
            CREATE TABLE branch_stock(id INTEGER PRIMARY KEY, branch_id INTEGER, barcode TEXT);
            CREATE TABLE customer_account_transactions(id INTEGER PRIMARY KEY, customer_id INTEGER);
            CREATE TABLE customer_account_invoices(id INTEGER PRIMARY KEY, customer_id INTEGER);
            CREATE TABLE audit_log(id INTEGER PRIMARY KEY, event_time TEXT, event_type TEXT);
        """)

    def tearDown(self):
        self.conn.close()

    def test_phase54_migration_creates_safe_indexes(self):
        self.assertEqual(migrate_connection(self.conn), 5)
        health = index_health(self.conn)
        self.assertTrue(health["ok"])
        self.assertEqual(health["missing"], [])

    def test_migration_is_idempotent(self):
        self.assertEqual(migrate_connection(self.conn), 5)
        self.assertEqual(migrate_connection(self.conn), 5)
        self.assertTrue(index_health(self.conn)["ok"])

    def test_missing_optional_tables_are_ignored(self):
        self.assertEqual(migrate_connection(self.conn), 5)
        self.assertFalse(any("loyalty" in x for x in index_health(self.conn)["missing"]))


if __name__ == "__main__":
    unittest.main()
