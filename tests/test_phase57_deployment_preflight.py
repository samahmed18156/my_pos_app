import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.deployment_preflight import (
    check_schema_version,
    run_deployment_preflight,
)


class Phase57DeploymentPreflightTests(unittest.TestCase):
    def test_missing_database_is_warn_not_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "missing.db"
            result = run_deployment_preflight(db_path=db, minimum_free_mb=1)
        self.assertEqual(result["phase"], 57)
        self.assertTrue(result["ready"])
        self.assertEqual(result["overall"], "WARN")
        self.assertTrue(result["read_only"])

    def test_schema_version_is_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "pos_store.db"
            conn = sqlite3.connect(db)
            conn.execute("PRAGMA user_version=3")
            conn.commit(); conn.close()
            result = check_schema_version(db)
            self.assertEqual(result.status, "OK")
            self.assertEqual(result.details["version"], 3)
            conn = sqlite3.connect(db)
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 3)
            conn.close()

    def test_corrupt_database_fails_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "pos_store.db"
            db.write_bytes(b"not a sqlite database")
            with patch("services.deployment_preflight.run_runtime_diagnostics", return_value={"overall": "OK"}):
                result = run_deployment_preflight(db_path=db, minimum_free_mb=1)
        self.assertFalse(result["ready"])
        self.assertEqual(result["overall"], "ERROR")
        self.assertTrue(any(c["name"] == "database_health" and c["status"] == "ERROR" for c in result["checks"]))

    def test_valid_database_reports_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "pos_store.db"
            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE products(barcode TEXT PRIMARY KEY, description TEXT, selling_price REAL, cost_price REAL, soh REAL)")
            conn.execute("PRAGMA user_version=3")
            conn.commit(); conn.close()
            healthy = {"ok": True, "problems": [], "sqlite": {"quick_check": "ok"}, "readiness": {}}
            with patch("services.deployment_preflight.run_runtime_diagnostics", return_value={"overall": "OK"}), \
                 patch("services.deployment_preflight.full_database_health", return_value=healthy):
                result = run_deployment_preflight(db_path=db, minimum_free_mb=1)
        self.assertTrue(result["ready"])
        self.assertEqual(result["overall"], "OK")
        self.assertEqual(result["phase"], 57)


if __name__ == "__main__":
    unittest.main()
