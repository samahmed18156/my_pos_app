import sqlite3
import unittest

from services.database_maintenance import (
    analyze_database,
    maintenance_report,
    optimize_database,
    vacuum_database,
)


class Phase55DatabaseMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("CREATE TABLE products(id INTEGER PRIMARY KEY, barcode TEXT, name TEXT)")
        self.conn.executemany("INSERT INTO products(barcode, name) VALUES (?, ?)", [(str(i), f"P{i}") for i in range(10)])
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_maintenance_report_is_read_only(self):
        before = self.conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        report = maintenance_report(self.conn)
        after = self.conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        self.assertTrue(report["ok"])
        self.assertEqual(before, after)
        self.assertFalse(report["in_transaction"])

    def test_analyze_succeeds_without_business_data_change(self):
        result = analyze_database(self.conn)
        self.assertTrue(result.ok)
        self.assertTrue(result.changed)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM products").fetchone()[0], 10)

    def test_optimize_succeeds(self):
        result = optimize_database(self.conn)
        self.assertTrue(result.ok)
        self.assertTrue(result.changed)

    def test_vacuum_refuses_active_transaction(self):
        self.conn.execute("INSERT INTO products(barcode, name) VALUES ('x', 'txn')")
        self.assertTrue(self.conn.in_transaction)
        result = vacuum_database(self.conn)
        self.assertFalse(result.ok)
        self.assertIn("transaction is active", result.detail)
        self.conn.rollback()

    def test_vacuum_succeeds_when_idle(self):
        result = vacuum_database(self.conn)
        self.assertTrue(result.ok)
        self.assertTrue(result.changed)


if __name__ == "__main__":
    unittest.main()
