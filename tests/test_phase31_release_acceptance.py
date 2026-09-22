import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

import database
from services.production_hardening import backup_database, restore_database, integrity_check, prune_backups


class Phase31ReleaseAcceptanceTests(unittest.TestCase):
    def _fresh_db(self, td):
        old = database.DB_PATH
        database.DB_PATH = os.path.join(td, 'pos_store.db')
        database.init_db()
        return old, database.DB_PATH

    def test_fresh_install_creates_usable_database(self):
        with tempfile.TemporaryDirectory() as td:
            old, path = self._fresh_db(td)
            try:
                self.assertTrue(os.path.isfile(path))
                self.assertTrue(integrity_check(path))
                con = sqlite3.connect(path)
                try:
                    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    self.assertTrue({'products','users','sales_history','sale_items','stock_movements','branches'} <= tables)
                    self.assertGreaterEqual(con.execute('SELECT COUNT(*) FROM users').fetchone()[0], 1)
                finally:
                    con.close()
            finally:
                database.DB_PATH = old

    def test_existing_database_initialization_preserves_business_data(self):
        with tempfile.TemporaryDirectory() as td:
            old, path = self._fresh_db(td)
            try:
                con = sqlite3.connect(path)
                con.execute("INSERT INTO products (barcode, description, cost_price, selling_price, soh) VALUES ('P31','Phase31 Product',10,15,7)")
                con.commit(); con.close()
                before = sqlite3.connect(path).execute("SELECT description, soh FROM products WHERE barcode='P31'").fetchone()
                database.init_db()
                after = sqlite3.connect(path).execute("SELECT description, soh FROM products WHERE barcode='P31'").fetchone()
                self.assertEqual(before, after)
                self.assertTrue(integrity_check(path))
            finally:
                database.DB_PATH = old

    def test_verified_backup_and_restore_round_trip(self):
        with tempfile.TemporaryDirectory() as td:
            old, path = self._fresh_db(td)
            try:
                con = sqlite3.connect(path)
                con.execute("INSERT INTO products (barcode, description, cost_price, selling_price, soh) VALUES ('B31','Backup Product',10,20,11)")
                con.commit(); con.close()
                backup = os.path.join(td, 'backup.db')
                backup_database(path, backup)
                self.assertTrue(integrity_check(backup))
                con = sqlite3.connect(path)
                con.execute("UPDATE products SET soh=99 WHERE barcode='B31'")
                con.commit(); con.close()
                safety = os.path.join(td, 'safety.db')
                restore_database(backup, path, safety)
                self.assertTrue(integrity_check(path))
                self.assertTrue(integrity_check(safety))
                self.assertEqual(sqlite3.connect(path).execute("SELECT soh FROM products WHERE barcode='B31'").fetchone()[0], 11)
            finally:
                database.DB_PATH = old

    def test_corrupt_database_is_not_accepted_as_verified_backup(self):
        with tempfile.TemporaryDirectory() as td:
            bad = os.path.join(td, 'corrupt.db')
            Path(bad).write_bytes(b'not a sqlite database')
            self.assertFalse(integrity_check(bad))
            with self.assertRaises(ValueError):
                restore_database(bad, os.path.join(td, 'target.db'))

    def test_backup_failure_does_not_replace_destination(self):
        with tempfile.TemporaryDirectory() as td:
            destination = os.path.join(td, 'destination.db')
            Path(destination).write_bytes(b'original')
            with self.assertRaises(FileNotFoundError):
                backup_database(os.path.join(td, 'missing.db'), destination)
            self.assertEqual(Path(destination).read_bytes(), b'original')

    def test_backup_retention_keeps_newest_files(self):
        with tempfile.TemporaryDirectory() as td:
            for i in range(5):
                p = Path(td) / f'b{i}.db'
                p.write_bytes(b'x')
                os.utime(p, (i + 1, i + 1))
            removed = prune_backups(td, keep=2)
            self.assertEqual(removed, 3)
            self.assertEqual(len(list(Path(td).glob('*.db'))), 2)

    def test_full_schema_integrity_and_foreign_keys_check(self):
        with tempfile.TemporaryDirectory() as td:
            old, path = self._fresh_db(td)
            try:
                con = sqlite3.connect(path)
                try:
                    self.assertEqual(con.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                    self.assertEqual(con.execute('PRAGMA foreign_key_check').fetchall(), [])
                finally:
                    con.close()
            finally:
                database.DB_PATH = old

    def test_release_artifacts_exist(self):
        base = Path(__file__).resolve().parents[1]
        for name in ('app.py','database.py','release_check.py','disaster_recovery.py','jasper_runtime'):
            with self.subTest(name=name):
                self.assertTrue((base / name).exists(), name)


if __name__ == '__main__':
    unittest.main()
