import unittest
from datetime import datetime
from services.ux_operational_polish import (
    APP_NAME, app_window_title, format_operator_status, format_last_refresh,
)


class Phase51UXTests(unittest.TestCase):
    def test_brand_is_bkpos(self):
        self.assertEqual(APP_NAME, "BKPOS")
        self.assertEqual(app_window_title(), "BKPOS")
        self.assertEqual(app_window_title("Main Store"), "BKPOS - Main Store")

    def test_operator_status(self):
        self.assertEqual(format_operator_status("Jane", "Cashier"), "Jane  •  Cashier")
        self.assertEqual(format_operator_status("Jane", ""), "Jane")
        self.assertEqual(format_operator_status(), "Operator")

    def test_refresh_timestamp_is_deterministic(self):
        dt = datetime(2026, 9, 11, 9, 22, 3)
        self.assertEqual(format_last_refresh(dt), "Last refreshed: 2026-09-11 09:22:03")


if __name__ == "__main__":
    unittest.main()
