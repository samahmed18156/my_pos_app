import sqlite3
import unittest

from services.sales_service import post_sale
from services.financial_service import void_sale
from services.branch_stock_service import ensure_schema as ensure_branch_schema


class FinalBusinessAuditTests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(":memory:")
        self.c.executescript("""
        CREATE TABLE branches(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        INSERT INTO branches VALUES(1,'Main Store');
        CREATE TABLE products(barcode TEXT PRIMARY KEY, description TEXT, selling_price REAL, cost_price REAL DEFAULT 0, soh REAL DEFAULT 0);
        INSERT INTO products VALUES('A','Widget',100,10,10);
        CREATE TABLE sales_history(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp TEXT,total_amount REAL,total_cost REAL,payment_type TEXT,cashier TEXT,customer_id INTEGER,customer_account TEXT,customer_name TEXT,branch_id INTEGER,branch_name TEXT,amount_tendered REAL,change_amount REAL,cash_amount REAL,card_amount REAL,voided INTEGER DEFAULT 0,voided_at TEXT,voided_by TEXT);
        CREATE TABLE sale_items(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER,barcode TEXT,description TEXT,qty REAL,price REAL,value REAL,cost_price REAL DEFAULT 0);
        CREATE TABLE stock_movements(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp TEXT,barcode TEXT,description TEXT,movement_type TEXT,qty REAL,qty_before REAL,qty_after REAL,cost_price REAL,reference TEXT,reason TEXT,cashier TEXT);
        CREATE TABLE return_items(id INTEGER PRIMARY KEY AUTOINCREMENT,return_id INTEGER,sale_item_id INTEGER,qty REAL);
        CREATE TABLE stock_transfers(id INTEGER PRIMARY KEY AUTOINCREMENT,transfer_no TEXT,from_branch INTEGER,to_branch INTEGER,barcode TEXT,description TEXT,qty REAL,status TEXT DEFAULT 'POSTED',cashier TEXT,timestamp DATETIME DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE customers(id INTEGER PRIMARY KEY,name TEXT,credit_limit REAL DEFAULT 0,active INTEGER DEFAULT 1);
        INSERT INTO customers VALUES(1,'Alice',500,1);
        CREATE TABLE customer_account_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,customer_id INTEGER,txn_date TEXT,txn_type TEXT,reference TEXT,description TEXT,debit REAL DEFAULT 0,credit REAL DEFAULT 0,balance_after REAL DEFAULT 0,cashier TEXT);
        CREATE TABLE customer_account_invoices(id INTEGER PRIMARY KEY AUTOINCREMENT,customer_id INTEGER,sale_id INTEGER UNIQUE,invoice_no TEXT,invoice_date TEXT,total REAL,paid REAL,outstanding REAL,status TEXT);
        CREATE TABLE void_history(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER,amount REAL,cash_amount REAL,card_amount REAL,cashier TEXT,reason TEXT);
        CREATE TABLE transaction_controls(id INTEGER PRIMARY KEY AUTOINCREMENT,control_type TEXT,reference TEXT,amount REAL,status TEXT,notes TEXT,cashier TEXT);
        """)
        ensure_branch_schema(self.c)

    def tearDown(self):
        self.c.close()

    def test_service_rejects_credit_sale_without_customer_before_writing_header(self):
        with self.assertRaises(ValueError):
            post_sale(self.c, cart=[{'code':'A','qty':1,'price':100,'value':100}], total=100,
                      total_cost=10, payment_info={}, payment_type='Credit Account')
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM sales_history').fetchone()[0], 0)

    def test_service_enforces_credit_limit(self):
        with self.assertRaises(ValueError):
            post_sale(self.c, cart=[{'code':'A','qty':1,'price':600,'value':600}], total=600,
                      total_cost=10, payment_info={}, payment_type='Credit Account', customer_id=1)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM sales_history').fetchone()[0], 0)

    def test_service_uses_quantity_times_price_as_authoritative_total(self):
        with self.assertRaises(ValueError):
            post_sale(self.c, cart=[{'code':'A','qty':1,'price':100,'value':100}], total=99,
                      total_cost=10, payment_info={'cash':99}, payment_type='Cash')
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM sales_history').fetchone()[0], 0)

    def test_void_credit_sale_reverses_debtor_balance(self):
        sid = post_sale(self.c, cart=[{'code':'A','qty':1,'price':100,'value':100}], total=100,
                        total_cost=10, payment_info={}, payment_type='Credit Account', customer_id=1,
                        customer_account='C-1', customer_name='Alice')
        self.c.commit()
        self.assertEqual(self.c.execute('SELECT outstanding,status FROM customer_account_invoices WHERE sale_id=?',(sid,)).fetchone(), (100.0,'UNPAID'))
        result = void_sale(self.c, sid, actor='manager', reason='Correction')
        self.c.commit()
        self.assertEqual(result['total'], 100.0)
        self.assertEqual(self.c.execute('SELECT total,paid,outstanding,status FROM customer_account_invoices WHERE sale_id=?',(sid,)).fetchone(), (0.0,0.0,0.0,'VOID'))
        self.assertEqual(self.c.execute('SELECT COALESCE(SUM(debit-credit),0) FROM customer_account_transactions WHERE customer_id=1').fetchone()[0], 0.0)

    def test_void_part_paid_credit_sale_preserves_customer_credit(self):
        sid = post_sale(self.c, cart=[{'code':'A','qty':1,'price':100,'value':100}], total=100,
                        total_cost=10, payment_info={}, payment_type='Credit Account', customer_id=1)
        self.c.commit()
        self.c.execute("INSERT INTO customer_account_transactions(customer_id,txn_type,reference,debit,credit,balance_after,cashier) VALUES(?,?,?,?,?,?,?)", (1,'PAYMENT','PAY-1',0,40,60,'alice'))
        self.c.execute("UPDATE customer_account_invoices SET paid=40, outstanding=60, status='PART PAID' WHERE sale_id=?", (sid,))
        self.c.commit()
        void_sale(self.c, sid, actor='manager', reason='Correction')
        self.c.commit()
        balance = self.c.execute('SELECT COALESCE(SUM(debit-credit),0) FROM customer_account_transactions WHERE customer_id=1').fetchone()[0]
        self.assertEqual(balance, -40.0)


if __name__ == '__main__':
    unittest.main()
