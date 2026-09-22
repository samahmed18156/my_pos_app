import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.runtime_diagnostics import (
    check_database_file,
    check_disk_space,
    run_runtime_diagnostics,
)


class Phase56RuntimeDiagnosticsTests(unittest.TestCase):
    def test_disk_space_returns_structured_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = check_disk_space(tmp, minimum_free_mb=1)
        self.assertEqual(result.name, "disk_space")
        self.assertIn(result.status, {"OK", "WARN"})
        self.assertIn("free_mb", result.details)

    def test_database_file_missing_is_warning(self):
        with patch("services.runtime_diagnostics.config.DB_PATH", "/definitely/missing/bkpos.db"):
            result = check_database_file()
        self.assertEqual(result.status, "WARN")
        self.assertIn("does not exist", result.message)

    def test_database_file_existing_readable(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "pos_store.db"
            db.write_bytes(b"BKPOS")
            with patch("services.runtime_diagnostics.config.DB_PATH", str(db)):
                result = check_database_file()
        self.assertEqual(result.status, "OK")
        self.assertEqual(result.details["size_bytes"], 5)

    def test_runtime_diagnostics_is_read_only_and_structured(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.multiple(
                "services.runtime_diagnostics.config",
                DATA_DIR=tmp,
                BACKUP_DIR=tmp,
                RECEIPT_DIR=tmp,
                GENERATED_REPORT_DIR=tmp,
                DB_PATH=str(Path(tmp) / "missing.db"),
            ):
                before = set(os.listdir(tmp))
                report = run_runtime_diagnostics(minimum_free_mb=1)
                after = set(os.listdir(tmp))
        self.assertEqual(before, after)
        self.assertEqual(report["phase"], 56)
        self.assertTrue(report["read_only"])
        self.assertIn(report["overall"], {"OK", "WARN", "ERROR"})
        self.assertGreaterEqual(len(report["checks"]), 6)


if __name__ == "__main__":
    unittest.main()
