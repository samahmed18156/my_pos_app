
import sqlite3
import unittest
from services.performance_tools import (
    benchmark_query, explain_query, table_indexes, time_call
)

class Phase53PerformanceTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.execute("CREATE TABLE products(id INTEGER PRIMARY KEY, barcode TEXT, name TEXT)")
        self.conn.execute("CREATE INDEX idx_products_barcode ON products(barcode)")
        self.conn.executemany(
            "INSERT INTO products(barcode,name) VALUES (?,?)",
            [(f"B{i}", f"Product {i}") for i in range(1000)]
        )
        self.conn.commit()

    def tearDown(self):
        self.conn.close()

    def test_timing(self):
        result, timing = time_call("items", lambda: [1,2,3])
        self.assertEqual(result, [1,2,3])
        self.assertGreaterEqual(timing.elapsed_ms, 0)

    def test_query_plan_is_read_only(self):
        plan = explain_query(
            self.conn, "SELECT * FROM products WHERE barcode = ?", ("B500",)
        )
        self.assertTrue(plan)

    def test_indexes_are_visible(self):
        names = {x["name"] for x in table_indexes(self.conn, "products")}
        self.assertIn("idx_products_barcode", names)

    def test_benchmark(self):
        timing = benchmark_query(
            self.conn, "SELECT * FROM products WHERE barcode = ?", ("B500",), 3
        )
        self.assertGreaterEqual(timing.elapsed_ms, 0)
        self.assertEqual(timing.result_count, 1)

if __name__ == "__main__":
    unittest.main()
