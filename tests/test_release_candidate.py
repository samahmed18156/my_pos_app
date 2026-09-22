import importlib
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

import database


class ReleaseCandidateTests(unittest.TestCase):
    def test_core_modules_import(self):
        modules = [
            "database", "login", "security", "permissions", "services.sales_service",
            "services.returns_service", "services.grn_service", "services.stock_service",
            "services.branch_stock_service", "services.accounts_service",
            "services.supplier_credit_service", "services.financial_reconciliation",
            "services.production_hardening", "disaster_recovery", "health_check",
        ]
        for name in modules:
            with self.subTest(module=name):
                importlib.import_module(name)

    def test_clean_first_launch_creates_usable_database(self):
        old = database.DB_PATH
        with tempfile.TemporaryDirectory() as td:
            database.DB_PATH = os.path.join(td, "pos_store.db")
            try:
                database.init_db()
                con = sqlite3.connect(database.DB_PATH)
                try:
                    self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    for table in ("products", "users", "sales_history", "sale_items", "stock_movements", "branches"):
                        self.assertIn(table, tables)
                    self.assertGreaterEqual(con.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
                finally:
                    con.close()
            finally:
                database.DB_PATH = old

    def test_clean_first_launch_is_repeatable(self):
        old = database.DB_PATH
        with tempfile.TemporaryDirectory() as td:
            database.DB_PATH = os.path.join(td, "pos_store.db")
            try:
                database.init_db()
                before = Path(database.DB_PATH).stat().st_size
                database.init_db()
                after = Path(database.DB_PATH).stat().st_size
                self.assertGreater(before, 0)
                self.assertGreater(after, 0)
                con = sqlite3.connect(database.DB_PATH)
                self.assertEqual(con.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
                self.assertEqual(con.execute("PRAGMA integrity_check").fetchone()[0], "ok")
                con.close()
            finally:
                database.DB_PATH = old


if __name__ == "__main__":
    unittest.main()
