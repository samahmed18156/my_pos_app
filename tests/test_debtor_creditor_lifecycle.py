import os, sqlite3, tempfile, unittest
from services import sales_service, returns_service, accounts_service
from services.financial_reconciliation import customer_balance, supplier_balance
from services import branch_stock_service


class DebtorCreditorLifecycleTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix='.db'); os.close(fd)
        self.c = sqlite3.connect(self.path)
        self.c.executescript('''
        CREATE TABLE branches(id INTEGER PRIMARY KEY,name TEXT); INSERT INTO branches VALUES(1,'Main');
        CREATE TABLE products(barcode TEXT PRIMARY KEY,description TEXT,cost_price REAL,selling_price REAL,soh REAL);
        INSERT INTO products VALUES('A','Widget',10,23,10);
        CREATE TABLE branch_stock(branch_id INTEGER,barcode TEXT,soh REAL,PRIMARY KEY(branch_id,barcode));
        CREATE TABLE stock_movements(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp TEXT,barcode TEXT,description TEXT,movement_type TEXT,qty REAL,qty_before REAL,qty_after REAL,cost_price REAL,reference TEXT,reason TEXT,cashier TEXT);
        CREATE TABLE sales_history(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp TEXT,total_amount REAL,total_cost REAL,payment_type TEXT,cashier TEXT,customer_id INTEGER,customer_account TEXT,customer_name TEXT,branch_id INTEGER,branch_name TEXT,cash_amount REAL DEFAULT 0,card_amount REAL DEFAULT 0,amount_tendered REAL DEFAULT 0,change_amount REAL DEFAULT 0,voided INTEGER DEFAULT 0);
        CREATE TABLE sale_items(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER,barcode TEXT,description TEXT,qty REAL,price REAL,value REAL);
        CREATE TABLE return_history(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp TEXT DEFAULT CURRENT_TIMESTAMP,original_sale_id INTEGER,total_amount REAL,refund_type TEXT,cashier TEXT,reason TEXT);
        CREATE TABLE return_items(id INTEGER PRIMARY KEY AUTOINCREMENT,return_id INTEGER,sale_item_id INTEGER,barcode TEXT,description TEXT,qty REAL,price REAL,value REAL);
        CREATE TABLE customers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,phone TEXT,address TEXT,email TEXT,credit_limit REAL DEFAULT 0,active INTEGER DEFAULT 1,created_at TEXT);
        CREATE TABLE customer_account_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,customer_id INTEGER,txn_date TEXT DEFAULT CURRENT_TIMESTAMP,txn_type TEXT,reference TEXT,description TEXT,debit REAL DEFAULT 0,credit REAL DEFAULT 0,balance_after REAL DEFAULT 0,cashier TEXT);
        CREATE TABLE customer_account_invoices(id INTEGER PRIMARY KEY AUTOINCREMENT,customer_id INTEGER,sale_id INTEGER UNIQUE,invoice_no TEXT,invoice_date TEXT,total REAL,paid REAL,outstanding REAL,status TEXT);
        CREATE TABLE customer_account_payments(id INTEGER PRIMARY KEY AUTOINCREMENT,customer_id INTEGER,payment_date TEXT DEFAULT CURRENT_TIMESTAMP,amount REAL,payment_method TEXT,reference TEXT,notes TEXT,cashier TEXT);
        CREATE TABLE customer_account_payment_allocations(id INTEGER PRIMARY KEY AUTOINCREMENT,payment_id INTEGER,invoice_id INTEGER,amount REAL);
        CREATE TABLE accounts(id INTEGER PRIMARY KEY,name TEXT,type TEXT,supplier_account_no TEXT,credit_limit REAL DEFAULT 0);
        CREATE TABLE account_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,account_id INTEGER,txn_type TEXT,total_amount REAL,txn_date TEXT);
        CREATE TABLE supplier_payments(id INTEGER PRIMARY KEY AUTOINCREMENT,payment_no TEXT,supplier_id INTEGER,supplier_account_no TEXT,supplier_name TEXT,payment_date TEXT,amount REAL,payment_method TEXT,reference TEXT,notes TEXT,cashier TEXT,created_by TEXT);
        CREATE TABLE supplier_credits(id INTEGER PRIMARY KEY AUTOINCREMENT,credit_no TEXT UNIQUE,supplier_id INTEGER,credit_date TEXT,amount REAL,reason TEXT,reference TEXT,created_by TEXT);
        ''')
        branch_stock_service.DB_NAME = self.path
        branch_stock_service.ensure_schema(self.c); self.c.commit()
        self.c.execute("INSERT INTO customers(name,credit_limit,active) VALUES('Alice',100,1)")
        self.cid = self.c.execute("SELECT id FROM customers").fetchone()[0]
        self.c.execute("INSERT INTO accounts(id,name,type,supplier_account_no,credit_limit) VALUES(9,'Supplier One','Supplier','SUP-001',1000)")
        self.c.commit()
        self.old_db = branch_stock_service.DB_NAME

    def tearDown(self):
        branch_stock_service.DB_NAME = self.old_db
        self.c.close(); os.unlink(self.path)

    def post_credit_sale(self, total=46):
        return sales_service.post_sale(self.c,
            cart=[{'code':'A','name':'Widget','qty':2,'price':23,'value':46}],
            total=total,total_cost=20,payment_info={},payment_type='Credit Account',
            cashier='alice',branch_id=1,branch_name='Main',customer_id=self.cid,
            customer_account='C001',customer_name='Alice')

    def test_credit_sale_payment_and_balance(self):
        sid=self.post_credit_sale(); self.c.commit()
        self.assertEqual(customer_balance(self.c,self.cid),46)
        result=accounts_service.customer_payment(self.c,customer_id=self.cid,amount=20,payment_method='Cash',reference='CP-1',cashier='alice')
        self.c.commit()
        self.assertEqual(result['balance'],26)
        inv=self.c.execute('SELECT total,paid,outstanding,status FROM customer_account_invoices WHERE sale_id=?',(sid,)).fetchone()
        self.assertEqual(inv,(46.0,20.0,26.0,'PART PAID'))

    def test_credit_sale_return_reduces_invoice_and_balance(self):
        sid=self.post_credit_sale(); self.c.commit()
        item=self.c.execute('SELECT id FROM sale_items WHERE sale_id=?',(sid,)).fetchone()[0]
        rid,total=returns_service.post_return(self.c,sale_id=sid,lines=[{'sale_item_id':item,'qty':1}],refund_type='Account Credit',cashier='alice')
        self.c.commit()
        self.assertEqual(total,23)
        inv=self.c.execute('SELECT total,paid,outstanding,status FROM customer_account_invoices WHERE sale_id=?',(sid,)).fetchone()
        self.assertEqual(inv,(23.0,0.0,23.0,'UNPAID'))
        self.assertEqual(customer_balance(self.c,self.cid),23)

    def test_customer_payment_rolls_back_when_too_large(self):
        self.post_credit_sale();
        with self.assertRaises(ValueError):
            accounts_service.customer_payment(self.c,customer_id=self.cid,amount=47)
        self.c.rollback()
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM customer_account_payments').fetchone()[0],0)
        self.assertEqual(customer_balance(self.c,self.cid),0)

    def test_supplier_purchase_credit_payment_lifecycle(self):
        self.c.execute("INSERT INTO account_transactions(account_id,txn_type,total_amount,txn_date) VALUES(9,'PURCHASE',500,'2026-09-07')")
        self.c.commit()
        self.assertEqual(supplier_balance(self.c,9),500)
        accounts_service.supplier_payment(self.c,supplier_id=9,amount=125,reference='SP-1',cashier='manager')
        self.c.commit()
        self.assertEqual(supplier_balance(self.c,9),375)
        accounts_service.supplier_credit(self.c,supplier_id=9,amount=50,credit_no='SCN-1',reason='Damaged goods',created_by='manager')
        self.c.commit()
        self.assertEqual(supplier_balance(self.c,9),325)

    def test_supplier_overpayment_is_rejected_without_advance_flag(self):
        self.c.execute("INSERT INTO account_transactions(account_id,txn_type,total_amount,txn_date) VALUES(9,'PURCHASE',100,'2026-09-07')")
        with self.assertRaises(ValueError):
            accounts_service.supplier_payment(self.c,supplier_id=9,amount=101,reference='SP-OVER')
        self.c.rollback()
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM supplier_payments").fetchone()[0],0)

    def test_supplier_advance_can_be_explicit(self):
        accounts_service.supplier_payment(self.c,supplier_id=9,amount=100,reference='ADV-1',allow_advance=True)
        self.c.commit()
        self.assertEqual(supplier_balance(self.c,9),-100)


if __name__=='__main__': unittest.main()
