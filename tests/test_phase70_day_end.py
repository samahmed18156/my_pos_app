import sqlite3
import tempfile
import unittest
from pathlib import Path

from services.day_end_procedure import check_open_shifts, check_cashup_variances, run_day_end
from services.operator_errors import operator_message


class Phase70Tests(unittest.TestCase):
    def base_db(self):
        c = sqlite3.connect(":memory:")
        c.executescript("""
        CREATE TABLE products(id INTEGER PRIMARY KEY, barcode TEXT, description TEXT, soh REAL, cost_price REAL);
        CREATE TABLE sales_history(id INTEGER PRIMARY KEY, timestamp TEXT, total_amount REAL, total_cost REAL);
        CREATE TABLE sale_items(id INTEGER PRIMARY KEY, sale_id INTEGER, barcode TEXT, qty REAL);
        CREATE TABLE grns(id INTEGER PRIMARY KEY);
        CREATE TABLE grn_items(id INTEGER PRIMARY KEY, grn_id INTEGER, barcode TEXT, qty REAL);
        CREATE TABLE stock_movements(id INTEGER PRIMARY KEY, barcode TEXT, qty REAL);
        CREATE TABLE cashier_shifts(id INTEGER PRIMARY KEY, cashier TEXT, opened_at TEXT, status TEXT);
        CREATE TABLE cashup_records(id INTEGER PRIMARY KEY, cashup_date TEXT, cashier TEXT, difference REAL, variance_reason TEXT);
        """)
        return c

    def test_open_shift_warning(self):
        c = self.base_db(); c.execute("INSERT INTO cashier_shifts VALUES(1,'Alice','2026-09-11 08:00','OPEN')")
        status, _, details = check_open_shifts(c)
        self.assertEqual(status, "WARN"); self.assertEqual(len(details["open_shifts"]), 1)

    def test_variance_warning(self):
        c = self.base_db(); c.execute("INSERT INTO cashup_records VALUES(1,'2026-09-11','Alice',10.0,'short')")
        status, _, details = check_cashup_variances(c)
        self.assertEqual(status, "WARN"); self.assertEqual(len(details["variances"]), 1)

    def test_operator_message(self):
        self.assertIn("already completed", operator_message("duplicate"))
        self.assertEqual(operator_message("unknown"), "The operation could not be completed safely.")

    def test_day_end_creates_verified_backup(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(dir="/dev/shm") as td:
            db = Path(td) / "pos_store.db"
            db.write_bytes(b"placeholder")
            fake_health = {"ok": True, "problems": [], "sqlite": {"quick_check": "ok"}, "readiness": {}}
            fake_backup = {"ok": True, "path": str(Path(td) / "day_end.db"), "size_bytes": 10, "health": {"ok": True}}
            with patch("services.day_end_procedure.full_database_health", return_value=fake_health), \
                 patch("services.day_end_procedure.create_verified_day_end_backup", return_value=fake_backup), \
                 patch("services.day_end_procedure._table_exists", return_value=False):
                result = run_day_end(db, optimize=False)
            self.assertTrue(result["ok"])
            self.assertTrue(result["backup"]["ok"])


if __name__ == '__main__':
    unittest.main()
