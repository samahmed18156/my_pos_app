import sqlite3, tempfile, unittest
from pathlib import Path
from services.release_hardening import preflight_database, create_release_backup

class ReleaseHardeningTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()

    def _db(self, complete=True):
        p=self.root/"pos_store.db"; c=sqlite3.connect(p)
        tables=["users","products","branches","stock_movements","sales","sale_items","customers","account_transactions"]
        if complete:
            for t in tables:
                c.execute(f"CREATE TABLE {t}(id INTEGER PRIMARY KEY)")
        else:
            c.execute("CREATE TABLE users(id INTEGER PRIMARY KEY)")
        c.commit(); c.close(); return p

    def test_preflight_accepts_core_schema(self):
        r=preflight_database(self._db(True)); self.assertTrue(r["ok"]); self.assertEqual(r["missing_tables"],[])

    def test_preflight_reports_missing_core_tables(self):
        r=preflight_database(self._db(False)); self.assertFalse(r["ok"]); self.assertIn("sales",r["missing_tables"])

    def test_preflight_reports_missing_database(self):
        r=preflight_database(self.root/"missing.db"); self.assertFalse(r["ok"])

    def test_release_backup_is_created_and_verified(self):
        db=self._db(True); out=create_release_backup(db,self.root/"backups",keep=3)
        self.assertTrue(Path(out).is_file())
        c=sqlite3.connect(out); self.assertTrue(c.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]>=8); c.close()

if __name__=="__main__": unittest.main()
