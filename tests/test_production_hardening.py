import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from services.production_hardening import backup_database, restore_database, integrity_check, prune_backups, require_permission


class ProductionHardeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.db = self.root / "pos_store.db"
        con = sqlite3.connect(self.db)
        con.execute("CREATE TABLE demo(id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        con.execute("INSERT INTO demo(value) VALUES ('original')")
        con.commit(); con.close()

    def tearDown(self):
        self.tmp.cleanup()

    def test_backup_is_verified_and_data_survives(self):
        backup = self.root / "backups" / "one.db"
        backup_database(self.db, backup)
        self.assertTrue(integrity_check(backup))
        con = sqlite3.connect(backup)
        self.assertEqual(con.execute("SELECT value FROM demo").fetchone()[0], "original")
        con.close()

    def test_restore_creates_safety_backup_and_restores(self):
        backup = self.root / "backup.db"
        backup_database(self.db, backup)
        con = sqlite3.connect(self.db); con.execute("UPDATE demo SET value='changed'"); con.commit(); con.close()
        safety = self.root / "safety.db"
        created = restore_database(backup, self.db, safety)
        self.assertEqual(str(safety), created)
        self.assertTrue(integrity_check(self.db)); self.assertTrue(integrity_check(safety))
        con = sqlite3.connect(self.db); self.assertEqual(con.execute("SELECT value FROM demo").fetchone()[0], "original"); con.close()

    def test_invalid_backup_is_rejected(self):
        bad = self.root / "bad.db"; bad.write_text("not sqlite")
        with self.assertRaises(ValueError): restore_database(bad, self.db)

    def test_backup_retention_keeps_newest(self):
        folder = self.root / "backups"; folder.mkdir()
        paths=[]
        for i in range(5):
            p=folder/f"b{i}.db"; p.write_text(str(i)); paths.append(p)
        # Force deterministic ordering by mtime.
        for i,p in enumerate(paths): os.utime(p,(100+i,100+i))
        removed=prune_backups(folder,keep=2)
        self.assertEqual(removed,3); self.assertEqual(len(list(folder.glob('*.db'))),2)

    def test_permission_helper_accepts_granted_permission(self):
        require_permission({"can_access_stock": True}, "can_access_stock")

    def test_permission_helper_rejects_missing_permission(self):
        with self.assertRaises(PermissionError): require_permission({}, "can_access_stock")

    def test_transaction_rolls_back_after_exception(self):
        con=sqlite3.connect(self.db)
        try:
            con.execute("BEGIN")
            con.execute("UPDATE demo SET value='temporary'")
            raise RuntimeError("simulated crash")
        except RuntimeError:
            con.rollback()
        finally:
            con.close()
        con=sqlite3.connect(self.db); self.assertEqual(con.execute("SELECT value FROM demo").fetchone()[0],"original"); con.close()


if __name__ == '__main__': unittest.main()
