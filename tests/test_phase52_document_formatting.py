import unittest
from services.document_formatting import validate_report_period, report_filename, empty_report_message


class Phase52DocumentFormattingTests(unittest.TestCase):
    def test_valid_period(self):
        self.assertEqual(validate_report_period("2026-09-01", "2026-09-11"), ("2026-09-01", "2026-09-11"))

    def test_inverted_period_rejected(self):
        with self.assertRaises(ValueError):
            validate_report_period("2026-09-12", "2026-09-11")

    def test_invalid_date_rejected(self):
        with self.assertRaises(ValueError):
            validate_report_period("11/09/2026", "2026-09-11")

    def test_filename_is_descriptive(self):
        self.assertEqual(report_filename("sales", "2026-09-01", "2026-09-11"),
                         "BKPOS_sales_2026-09-01_to_2026-09-11.pdf")

    def test_empty_report_message(self):
        self.assertIn("No records were found", empty_report_message("Sales Report"))


if __name__ == "__main__":
    unittest.main()
