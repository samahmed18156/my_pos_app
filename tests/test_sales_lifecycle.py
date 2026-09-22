import os
import sqlite3
import tempfile
import unittest

from services import branch_stock_service
from services import sales_service
import customer_accounts


class SalesLifecycleTests(unittest.TestCase):
    def setUp(self):
        fd, self.db = tempfile.mkstemp(suffix='.db'); os.close(fd)
        self.conn = sqlite3.connect(self.db)
        self.conn.executescript('''
            CREATE TABLE branches(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
            INSERT INTO branches VALUES(1,'Main Store'),(2,'Branch 2');
            CREATE TABLE products(
                barcode TEXT PRIMARY KEY, description TEXT NOT NULL,
                selling_price REAL NOT NULL, cost_price REAL DEFAULT 0, soh REAL DEFAULT 0);
            INSERT INTO products VALUES('100','Coffee',20,10,10);
            CREATE TABLE sales_history(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                total_amount REAL,total_cost REAL,payment_type TEXT,
                cashier TEXT,branch_id INTEGER,branch_name TEXT,
                customer_id INTEGER,customer_account TEXT,customer_name TEXT,
                amount_tendered REAL DEFAULT 0,change_amount REAL DEFAULT 0,
                cash_amount REAL DEFAULT 0,card_amount REAL DEFAULT 0,
                voided INTEGER DEFAULT 0,voided_at DATETIME,voided_by TEXT);
            CREATE TABLE sale_items(
                id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER,barcode TEXT,
                description TEXT,qty REAL,price REAL,value REAL);
            CREATE TABLE stock_movements(
                id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                barcode TEXT,description TEXT,movement_type TEXT,qty REAL,qty_before REAL,
                qty_after REAL,cost_price REAL,reference TEXT,reason TEXT,cashier TEXT);
            CREATE TABLE customers(
                id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,phone TEXT,address TEXT,email TEXT,
                credit_limit REAL DEFAULT 0,active INTEGER DEFAULT 1,created_at DATETIME DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE customer_account_transactions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,customer_id INTEGER,txn_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                txn_type TEXT,reference TEXT,description TEXT,debit REAL DEFAULT 0,credit REAL DEFAULT 0,
                balance_after REAL DEFAULT 0,cashier TEXT DEFAULT 'Unknown');
            CREATE TABLE customer_account_invoices(
                id INTEGER PRIMARY KEY AUTOINCREMENT,customer_id INTEGER,sale_id INTEGER UNIQUE,
                invoice_no TEXT,invoice_date DATETIME DEFAULT CURRENT_TIMESTAMP,total REAL,paid REAL,
                outstanding REAL,status TEXT);
        ''')
        self.conn.commit()
        self.old_branch_db = branch_stock_service.DB_NAME
        self.old_customer_db = customer_accounts.DB_NAME
        branch_stock_service.DB_NAME = self.db
        customer_accounts.DB_NAME = self.db
        branch_stock_service.ensure_schema(self.conn)
        self.conn.commit()

    def tearDown(self):
        branch_stock_service.DB_NAME = self.old_branch_db
        customer_accounts.DB_NAME = self.old_customer_db
        self.conn.close(); os.unlink(self.db)

    def sale(self, **overrides):
        args = dict(cart=[{'code':'100','name':'Coffee','qty':2,'price':20,'value':40}],
                    total=40,total_cost=20,
                    payment_info={'cash':40,'card':0,'amount_tendered':50,'change':10},
                    payment_type='Cash',cashier='alice',branch_id=1,branch_name='Main Store')
        args.update(overrides)
        return sales_service.post_sale(self.conn, **args)

    def test_cash_sale_writes_header_items_payment_and_stock(self):
        sid = self.sale(); self.conn.commit()
        h = self.conn.execute('SELECT total_amount,total_cost,payment_type,cash_amount,card_amount,amount_tendered,change_amount,branch_id FROM sales_history WHERE id=?',(sid,)).fetchone()
        item = self.conn.execute('SELECT barcode,qty,price,value FROM sale_items WHERE sale_id=?',(sid,)).fetchone()
        self.assertEqual(h, (40.0,20.0,'Cash',40.0,0.0,50.0,10.0,1))
        self.assertEqual(item, ('100',2.0,20.0,40.0))
        self.assertEqual(self.conn.execute('SELECT soh FROM products WHERE barcode="100"').fetchone()[0],8.0)
        self.assertEqual(self.conn.execute('SELECT soh FROM branch_stock WHERE branch_id=1 AND barcode="100"').fetchone()[0],8.0)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM stock_movements WHERE reference=?',(f'SALE #{sid}',)).fetchone()[0],1)

    def test_card_sale_records_card_and_no_cash(self):
        sid = self.sale(payment_type='Card', payment_info={'card':40,'cash':0,'amount_tendered':40,'change':0})
        row=self.conn.execute('SELECT cash_amount,card_amount FROM sales_history WHERE id=?',(sid,)).fetchone()
        self.assertEqual(row,(0.0,40.0))

    def test_split_payment_must_balance(self):
        with self.assertRaises(ValueError):
            self.sale(payment_type='Split Payment', payment_info={'cash':10,'card':20})
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sales_history').fetchone()[0],0)
        self.assertEqual(self.conn.execute('SELECT soh FROM products WHERE barcode="100"').fetchone()[0],10.0)

    def test_insufficient_stock_rolls_back_everything(self):
        with self.assertRaises(ValueError):
            self.sale(cart=[{'code':'100','name':'Coffee','qty':11,'price':20,'value':220}],total=220,total_cost=110,
                      payment_info={'cash':220,'amount_tendered':220,'change':0})
        self.conn.rollback()
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sales_history').fetchone()[0],0)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sale_items').fetchone()[0],0)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM stock_movements').fetchone()[0],0)
        self.assertEqual(self.conn.execute('SELECT soh FROM products WHERE barcode="100"').fetchone()[0],10.0)

    def test_unknown_product_rolls_back_header(self):
        with self.assertRaises(ValueError):
            self.sale(cart=[{'code':'999','name':'Missing','qty':1,'price':5,'value':5}],total=5,total_cost=2,
                      payment_info={'cash':5,'amount_tendered':5,'change':0})
        self.conn.rollback()
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sales_history').fetchone()[0],0)

    def test_credit_sale_posts_customer_ledger_and_invoice(self):
        self.conn.execute("INSERT INTO customers(name,credit_limit,active) VALUES('Bob',100,1)")
        cid=self.conn.execute("SELECT id FROM customers WHERE name='Bob'").fetchone()[0]
        sid=self.sale(payment_type='Credit Account',payment_info={},customer_id=cid,customer_account='C001',customer_name='Bob')
        row=self.conn.execute('SELECT customer_id,total_amount FROM sales_history WHERE id=?',(sid,)).fetchone()
        ledger=self.conn.execute('SELECT txn_type,debit,credit,reference FROM customer_account_transactions').fetchone()
        inv=self.conn.execute('SELECT sale_id,total,outstanding,status FROM customer_account_invoices').fetchone()
        self.assertEqual(row,(cid,40.0)); self.assertEqual(ledger,('INVOICE',40.0,0.0,f'INV-{sid:06d}'))
        self.assertEqual(inv,(sid,40.0,40.0,'UNPAID'))

    def test_credit_sale_rolls_back_ledger_when_stock_fails(self):
        self.conn.execute("INSERT INTO customers(name,credit_limit,active) VALUES('Bob',100,1)")
        cid=self.conn.execute("SELECT id FROM customers WHERE name='Bob'").fetchone()[0]
        with self.assertRaises(ValueError):
            self.sale(payment_type='Credit Account',payment_info={},customer_id=cid,customer_account='C001',customer_name='Bob',
                      cart=[{'code':'100','name':'Coffee','qty':11,'price':20,'value':220}],total=220,total_cost=110)
        self.conn.rollback()
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sales_history').fetchone()[0],0)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM customer_account_transactions').fetchone()[0],0)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM customer_account_invoices').fetchone()[0],0)

    def test_branch_sale_only_changes_selected_branch(self):
        # Move five units to branch 2 first, preserving global total.
        branch_stock_service.transfer(self.conn,1,2,'100',5,'admin'); self.conn.commit()
        sid=self.sale(branch_id=2,branch_name='Branch 2')
        self.conn.commit()
        b1=self.conn.execute('SELECT soh FROM branch_stock WHERE branch_id=1 AND barcode="100"').fetchone()[0]
        b2=self.conn.execute('SELECT soh FROM branch_stock WHERE branch_id=2 AND barcode="100"').fetchone()[0]
        global_soh=self.conn.execute('SELECT soh FROM products WHERE barcode="100"').fetchone()[0]
        self.assertEqual((b1,b2,global_soh),(5.0,3.0,8.0))
        self.assertEqual(self.conn.execute('SELECT branch_id FROM sales_history WHERE id=?',(sid,)).fetchone()[0],2)

    def test_transaction_rollback_after_partial_multi_item_sale(self):
        self.conn.execute("INSERT INTO products VALUES('200','Tea',15,7,3)")
        branch_stock_service.ensure_schema(self.conn); self.conn.commit()
        with self.assertRaises(ValueError):
            self.sale(cart=[{'code':'100','name':'Coffee','qty':2,'price':20,'value':40},
                            {'code':'200','name':'Tea','qty':4,'price':15,'value':60}],
                      total=100,total_cost=48,payment_info={'cash':100,'amount_tendered':100,'change':0})
        self.conn.rollback()
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM sales_history').fetchone()[0],0)
        self.assertEqual(self.conn.execute('SELECT soh FROM products WHERE barcode="100"').fetchone()[0],10.0)
        self.assertEqual(self.conn.execute('SELECT soh FROM products WHERE barcode="200"').fetchone()[0],3.0)


if __name__ == '__main__':
    unittest.main()
