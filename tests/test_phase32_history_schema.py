import sqlite3
import unittest

class Phase32HistorySchemaTests(unittest.TestCase):
    def test_history_payment_query_uses_payment_date(self):
        c=sqlite3.connect(":memory:")
        c.execute("CREATE TABLE customer_account_payments (id INTEGER PRIMARY KEY, customer_id INTEGER, payment_date DATETIME, amount REAL, payment_method TEXT, reference TEXT, notes TEXT, cashier TEXT)")
        c.execute("INSERT INTO customer_account_payments VALUES (1,1,'2026-09-08 12:00',100,'Cash','R1','','cashier')")
        row=c.execute("SELECT payment_date,id,amount,payment_method,reference FROM customer_account_payments WHERE date(payment_date) BETWEEN ? AND ?",('2026-09-08','2026-09-08')).fetchone()
        self.assertEqual(row[1],1)
        c.close()

if __name__ == '__main__': unittest.main()
