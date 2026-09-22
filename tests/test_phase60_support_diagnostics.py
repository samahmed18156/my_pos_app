import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.support_diagnostics import (
    collect_support_diagnostics,
    format_support_report,
    write_support_report,
)


class Phase60SupportDiagnosticsTests(unittest.TestCase):
    def test_format_report_redacts_secret_text(self):
        report = format_support_report({
            "generated_at": "2026-01-01T10:00:00",
            "app_version": "10.0.0",
            "python_version": "3.13",
            "platform": "Windows",
            "machine": "AMD64",
            "frozen": True,
            "database_exists": True,
            "logging": {"password": "should-not-appear", "file_logging": True},
            "runtime_checks": {"status": "ok"},
            "database_health": {"ok": True},
        })
        self.assertIn("BKPOS SUPPORT DIAGNOSTIC REPORT", report)
        self.assertNotIn("should-not-appear", report)

    def test_collect_has_expected_sections(self):
        with patch("services.support_diagnostics.run_runtime_diagnostics", return_value={"ok": True}), \
             patch("services.support_diagnostics.run_health_check", return_value={"ok": True}), \
             patch("services.support_diagnostics.logging_status", return_value={"file_logging": True}):
            result = collect_support_diagnostics()
        self.assertIn("runtime_checks", result)
        self.assertIn("database_health", result)
        self.assertIn("logging", result)
        self.assertIn("database_exists", result)

    def test_write_support_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("services.support_diagnostics.run_runtime_diagnostics", return_value={"ok": True}), \
                 patch("services.support_diagnostics.run_health_check", return_value={"ok": True}), \
                 patch("services.support_diagnostics.logging_status", return_value={"file_logging": True}):
                path = write_support_report(tmp)
            self.assertTrue(Path(path).is_file())
            self.assertIn("BKPOS SUPPORT DIAGNOSTIC REPORT", Path(path).read_text(encoding="utf-8"))
            self.assertTrue(Path(path).name.startswith("bkpos_support_"))


if __name__ == "__main__":
    unittest.main()


def test_support_diagnostics_includes_lifecycle(monkeypatch):
    import services.support_diagnostics as sd
    monkeypatch.setattr(sd, "run_runtime_diagnostics", lambda: {"ok": True})
    monkeypatch.setattr(sd, "run_health_check", lambda path: {"ok": True})
    monkeypatch.setattr(sd, "logging_status", lambda: {"file_logging": True, "writable": True})
    monkeypatch.setattr(sd, "lifecycle_status", lambda: {"status": "running", "previous_clean": True})
    data = sd.collect_support_diagnostics()
    assert data["lifecycle"]["status"] == "running"
    report = sd.format_support_report(data)
    assert "LIFECYCLE" in report
    assert "status: running" in report
