import os
import unittest
from unittest.mock import patch

from services.receipt_printing import configured_printer_name, printer_diagnostics, safe_print_receipt


class TestPhase68ReceiptPrinting(unittest.TestCase):
    def test_configurable_printer_name(self):
        with patch.dict(os.environ, {"BKPOS_RECEIPT_PRINTER": "Test Thermal"}):
            self.assertEqual(configured_printer_name(), "Test Thermal")

    def test_missing_printer_is_diagnosed_without_printing(self):
        with patch("receipt_printer.win32print", None):
            result = printer_diagnostics("Test Thermal")
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "UNAVAILABLE")

    def test_print_failure_is_returned_without_retry(self):
        with patch("receipt_printer.print_receipt", side_effect=RuntimeError("paper out")) as mocked:
            result = safe_print_receipt(items=[], total=1, payment_type="Cash")
        self.assertFalse(result.success)
        self.assertEqual(result.status, "FAILED")
        self.assertIn("paper out", result.message)
        mocked.assert_called_once()


if __name__ == "__main__":
    unittest.main()
