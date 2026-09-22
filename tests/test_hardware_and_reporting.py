import tempfile
import unittest
from pathlib import Path

import receipt_printer
from jasper_reports import jasper_receipt


class OutputIntegrationTests(unittest.TestCase):
    def test_printer_check_is_safe_without_windows_printer_stack(self):
        # CI/Linux/headless machines must fail safely rather than crash.
        if receipt_printer.win32print is None:
            self.assertFalse(receipt_printer.printer_exists())
            self.assertEqual(receipt_printer.get_installed_printers(), [])
        else:
            self.assertIsInstance(receipt_printer.get_installed_printers(), list)

    def test_jasper_receipt_xml_is_generated(self):
        xml = jasper_receipt.build_jrpxml(
            invoice_number="TEST-1001",
            items=[{"barcode":"1001", "description":"Test Product", "qty":2, "price":15.0, "value":30.0}],
            total=30.0,
            payment_type="Cash",
            payment_info={"amount_tendered":50, "change":20},
        )
        self.assertTrue(xml.startswith(b"<?xml"))
        self.assertIn(b"TEST-1001", xml)
        self.assertIn(b"30.00", xml)

    def test_jasper_viewer_missing_runtime_fails_cleanly(self):
        old = jasper_receipt.find_jasper_viewer
        old_status = jasper_receipt.jasper_viewer_status
        try:
            jasper_receipt.find_jasper_viewer = lambda: None
            jasper_receipt.jasper_viewer_status = lambda: (False, 'JasperReports/JasperViewer was not found')
            ok, message = jasper_receipt.open_in_jasperviewer(Path("missing-test.jrpxml"))
            self.assertFalse(ok)
            self.assertIn("JasperReports/JasperViewer was not found", message)
        finally:
            jasper_receipt.find_jasper_viewer = old
            jasper_receipt.jasper_viewer_status = old_status


if __name__ == "__main__":
    unittest.main()
