import os
import unittest
from unittest.mock import patch

from services.receipt_printing import configured_printer_name


class TestPhase81PrinterConnection(unittest.TestCase):
    def test_tt70_windows_queue_is_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(configured_printer_name(), "POS-80C")

    def test_existing_override_is_preserved(self):
        with patch.dict(os.environ, {"BKPOS_RECEIPT_PRINTER": "Another Queue"}):
            self.assertEqual(configured_printer_name(), "Another Queue")


if __name__ == "__main__":
    unittest.main()
