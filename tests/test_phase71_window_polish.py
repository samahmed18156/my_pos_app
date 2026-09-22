import unittest

from ui.window_polish import polished_title


class Phase71WindowPolishTests(unittest.TestCase):
    def test_title_prefix(self):
        self.assertEqual(polished_title("History"), "BKPOS • History")

    def test_title_not_double_prefixed(self):
        title = "BKPOS • History"
        self.assertEqual(polished_title(title), title)

    def test_bkpos_title_unchanged(self):
        self.assertEqual(polished_title("BKPOS"), "BKPOS")


if __name__ == "__main__":
    unittest.main()
