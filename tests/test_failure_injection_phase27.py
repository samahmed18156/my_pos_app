import sqlite3
import unittest

from services.sales_service import post_sale
from services.grn_service import post_grn
from services.returns_service import post_return
from services.branch_stock_service import ensure_schema as ensure_branch_schema


class FailureInjectionPhase27Tests(unittest.TestCase):
    """Prove failed multi-step postings leave no committed partial state.

    The production UI opens a transaction, calls the service, commits only on
    success, and rolls back on exception. These tests deliberately inject
    failures after earlier writes to verify that contract.
    """

    def setUp(self):
        self.c = sqlite3.connect(":memory:")
        self.c.executescript("""
        CREATE TABLE branches(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
        INSERT INTO branches VALUES(1,'Main Store');
        CREATE TABLE products(barcode TEXT PRIMARY KEY, description TEXT, selling_price REAL, cost_price REAL DEFAULT 0, soh REAL DEFAULT 0);
        INSERT INTO products VALUES('A','Widget',100,10,10),('B','Cable',50,5,10);
        CREATE TABLE sales_history(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp TEXT,total_amount REAL,total_cost REAL,payment_type TEXT,cashier TEXT,customer_id INTEGER,customer_account TEXT,customer_name TEXT,branch_id INTEGER,branch_name TEXT,amount_tendered REAL,change_amount REAL,cash_amount REAL,card_amount REAL,voided INTEGER DEFAULT 0);
        CREATE TABLE sale_items(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER,barcode TEXT,description TEXT,qty REAL,price REAL,value REAL,cost_price REAL DEFAULT 0);
        CREATE TABLE stock_movements(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp TEXT,barcode TEXT,description TEXT,movement_type TEXT,qty REAL,qty_before REAL,qty_after REAL,cost_price REAL,reference TEXT,reason TEXT,cashier TEXT);
        CREATE TABLE grn_headers(id INTEGER PRIMARY KEY AUTOINCREMENT,grn_no TEXT UNIQUE,supplier_id INTEGER,supplier_account TEXT,supplier_name TEXT,supplier_invoice TEXT,reference TEXT,vat_mode TEXT,subtotal REAL,vat REAL,total REAL,created_at TEXT,cashier TEXT,paid REAL DEFAULT 0,outstanding REAL DEFAULT 0,status TEXT DEFAULT 'UNPAID');
        CREATE TABLE grn_items(id INTEGER PRIMARY KEY AUTOINCREMENT,grn_id INTEGER,barcode TEXT,description TEXT,soh_before REAL,order_qty REAL,qty_received REAL,cost_price REAL,value REAL);
        CREATE TABLE account_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,account_id INTEGER,txn_type TEXT,total_amount REAL,txn_date TEXT);
        CREATE TABLE return_history(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp TEXT,original_sale_id INTEGER,total_amount REAL,refund_type TEXT,cashier TEXT,reason TEXT);
        CREATE TABLE return_items(id INTEGER PRIMARY KEY AUTOINCREMENT,return_id INTEGER,sale_item_id INTEGER,barcode TEXT,description TEXT,qty REAL,price REAL,value REAL);
        CREATE TABLE customers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,credit_limit REAL DEFAULT 0,active INTEGER DEFAULT 1);
        CREATE TABLE customer_account_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,customer_id INTEGER,txn_date TEXT,txn_type TEXT,reference TEXT,description TEXT,debit REAL DEFAULT 0,credit REAL DEFAULT 0,balance_after REAL DEFAULT 0,cashier TEXT);
        CREATE TABLE customer_account_invoices(id INTEGER PRIMARY KEY AUTOINCREMENT,customer_id INTEGER,sale_id INTEGER UNIQUE,invoice_no TEXT,invoice_date TEXT,total REAL,paid REAL,outstanding REAL,status TEXT);
        """)
        ensure_branch_schema(self.c)
        self.c.commit()

    def tearDown(self):
        self.c.close()

    def _counts(self):
        return tuple(self.c.execute("SELECT (SELECT COUNT(*) FROM sales_history),(SELECT COUNT(*) FROM sale_items),(SELECT COUNT(*) FROM stock_movements),(SELECT COUNT(*) FROM grn_headers),(SELECT COUNT(*) FROM grn_items),(SELECT COUNT(*) FROM account_transactions),(SELECT COUNT(*) FROM return_history),(SELECT COUNT(*) FROM return_items)").fetchone())

    def test_sale_failure_on_second_item_rolls_back_header_first_item_and_stock(self):
        self.c.execute("CREATE TRIGGER fail_second_sale_movement AFTER INSERT ON stock_movements WHEN NEW.movement_type='SALE' AND NEW.barcode='B' BEGIN SELECT RAISE(ABORT,'simulated printer/database failure'); END;")
        self.c.execute("BEGIN")
        with self.assertRaises(sqlite3.IntegrityError):
            post_sale(self.c, cart=[{'code':'A','name':'Widget','qty':1,'price':100,'value':100},{'code':'B','name':'Cable','qty':1,'price':50,'value':50}], total=150,total_cost=15,payment_info={'cash':150},payment_type='Cash',cashier='tester')
        self.c.rollback()
        self.assertEqual(self._counts(), (0,0,0,0,0,0,0,0))
        self.assertEqual(tuple(self.c.execute("SELECT soh,cost_price FROM products ORDER BY barcode").fetchall()), ((10.0,10.0),(10.0,5.0)))

    def test_grn_failure_on_second_item_rolls_back_header_first_item_stock_cost_and_supplier_ledger(self):
        self.c.execute("CREATE TRIGGER fail_second_grn_movement AFTER INSERT ON stock_movements WHEN NEW.movement_type='GRN' AND NEW.barcode='B' BEGIN SELECT RAISE(ABORT,'simulated database failure'); END;")
        self.c.execute("BEGIN")
        with self.assertRaises(sqlite3.IntegrityError):
            post_grn(self.c, supplier_id=7,supplier_account='SUP-7',supplier_name='Supplier',items=[{'barcode':'A','qty':2,'cost':20},{'barcode':'B','qty':2,'cost':10}],grn_no='GRN-FAIL')
        self.c.rollback()
        self.assertEqual(self._counts(), (0,0,0,0,0,0,0,0))
        self.assertEqual(tuple(self.c.execute("SELECT soh,cost_price FROM products ORDER BY barcode").fetchall()), ((10.0,10.0),(10.0,5.0)))

    def test_return_failure_on_stock_write_rolls_back_return_credit_and_stock(self):
        sid = post_sale(self.c, cart=[{'code':'A','name':'Widget','qty':2,'price':100,'value':200}], total=200,total_cost=20,payment_info={'cash':200},payment_type='Cash',cashier='tester')
        self.c.commit()
        item_id = self.c.execute("SELECT id FROM sale_items WHERE sale_id=?",(sid,)).fetchone()[0]
        self.c.execute("CREATE TRIGGER fail_return_movement AFTER INSERT ON stock_movements WHEN NEW.movement_type='RETURN' BEGIN SELECT RAISE(ABORT,'simulated stock write failure'); END;")
        before_counts = self._counts()
        before_soh = self.c.execute("SELECT soh FROM products WHERE barcode='A'").fetchone()[0]
        self.c.execute("BEGIN")
        with self.assertRaises(sqlite3.IntegrityError):
            post_return(self.c, sale_id=sid, lines=[{'sale_item_id':item_id,'qty':1}], refund_type='Cash Refund', cashier='tester')
        self.c.rollback()
        self.assertEqual(self._counts(), before_counts)
        self.assertEqual(self.c.execute("SELECT soh FROM products WHERE barcode='A'").fetchone()[0], before_soh)

    def test_duplicate_grn_number_can_be_rejected_without_partial_data(self):
        post_grn(self.c, supplier_id=7,supplier_account='SUP-7',supplier_name='Supplier',items=[{'barcode':'A','qty':1,'cost':20}],grn_no='GRN-1')
        self.c.commit()
        before = self._counts()
        self.c.execute("BEGIN")
        with self.assertRaises(sqlite3.IntegrityError):
            post_grn(self.c, supplier_id=7,supplier_account='SUP-7',supplier_name='Supplier',items=[{'barcode':'B','qty':1,'cost':10}],grn_no='GRN-1')
        self.c.rollback()
        self.assertEqual(self._counts(), before)
        self.assertEqual(self.c.execute("SELECT soh FROM products WHERE barcode='B'").fetchone()[0], 10.0)


if __name__ == '__main__':
    unittest.main()
