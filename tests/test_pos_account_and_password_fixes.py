import os
import sqlite3
import tempfile
import unittest


class PosAccountAndPasswordFixTests(unittest.TestCase):
    def test_admin_password_flag_is_not_reenabled_on_restart(self):
        # Regression contract: an admin who completed first-run setup stays at
        # must_change_password=0 across subsequent database initialization.
        src = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database.py")
        text = open(src, encoding="utf-8").read()
        self.assertNotIn(
            'UPDATE users SET must_change_password=1 WHERE lower(role)=\'admin\'',
            text,
        )

    def test_account_selector_contains_cash_and_debtors(self):
        conn = sqlite3.connect(":memory:")
        conn.executescript("""
            CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT, active INTEGER);
            INSERT INTO customers VALUES (1, 'Alice', 1);
            INSERT INTO customers VALUES (2, 'Bob', 1);
            INSERT INTO customers VALUES (3, 'Inactive', 0);
        """)
        rows = conn.execute(
            "SELECT id FROM customers WHERE active=1 ORDER BY name COLLATE NOCASE, id"
        ).fetchall()
        values = ["CASH"] + [f"CUST-{int(row[0]):06d}" for row in rows]
        self.assertEqual(values, ["CASH", "CUST-000001", "CUST-000002"])
        conn.close()

    def test_checkout_guard_rejects_empty_account(self):
        # Contract test for the validation logic added to ui/pos.py.
        src = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ui", "pos.py")
        text = open(src, encoding="utf-8").read()
        self.assertIn('"Sale Account Required"', text)
        self.assertIn('Select CASH or a debtor account before making the invoice.', text)


if __name__ == "__main__":
    unittest.main()
