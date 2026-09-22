import os, sqlite3, tempfile, unittest
from services.financial_reconciliation import financial_summary, sales_summary, customer_balance, supplier_balance

class FinancialReconciliationTests(unittest.TestCase):
    def setUp(self):
        f=tempfile.NamedTemporaryFile(delete=False); f.close(); self.path=f.name
        self.c=sqlite3.connect(self.path)
        self.c.executescript('''
        CREATE TABLE products(barcode TEXT PRIMARY KEY, cost_price REAL);
        CREATE TABLE sales_history(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp TEXT,total_amount REAL,total_cost REAL,payment_type TEXT,cashier TEXT,customer_id INTEGER,customer_account TEXT,customer_name TEXT,branch_id INTEGER,branch_name TEXT,amount_tendered REAL,change_amount REAL,cash_amount REAL,card_amount REAL,voided INTEGER DEFAULT 0);
        CREATE TABLE sale_items(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER,barcode TEXT,description TEXT,qty REAL,price REAL,value REAL);
        CREATE TABLE return_history(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp TEXT,original_sale_id INTEGER,total_amount REAL,refund_type TEXT,cashier TEXT);
        CREATE TABLE return_items(id INTEGER PRIMARY KEY AUTOINCREMENT,return_id INTEGER,sale_item_id INTEGER,barcode TEXT,description TEXT,qty REAL,price REAL,value REAL);
        CREATE TABLE customer_account_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,customer_id INTEGER,debit REAL DEFAULT 0,credit REAL DEFAULT 0);
        CREATE TABLE account_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,account_id INTEGER,txn_type TEXT,total_amount REAL,txn_date TEXT);
        CREATE TABLE operating_expenses(id INTEGER PRIMARY KEY AUTOINCREMENT,expense_date TEXT,total_amount REAL,vat_amount REAL,branch_id INTEGER);
        CREATE TABLE branches(id INTEGER PRIMARY KEY,name TEXT);
        INSERT INTO products VALUES('A',10);
        INSERT INTO branches VALUES(1,'Main'),(2,'Branch 2');
        ''')
        self.c.execute("INSERT INTO sales_history(timestamp,total_amount,total_cost,payment_type,cashier,branch_id,branch_name,cash_amount,card_amount) VALUES('2026-09-07 10:00',115,50,'Cash','alice',1,'Main',115,0)")
        sid=self.c.execute('SELECT last_insert_rowid()').fetchone()[0]
        self.c.execute("INSERT INTO sale_items(sale_id,barcode,description,qty,price,value) VALUES(?,?,?,?,?,?)",(sid,'A','Item',5,23,115))
        self.c.execute("INSERT INTO sales_history(timestamp,total_amount,total_cost,payment_type,cashier,branch_id,branch_name,cash_amount,card_amount) VALUES('2026-09-07 11:00',100,40,'Card','bob',2,'Branch 2',0,100)")
        self.c.execute("INSERT INTO operating_expenses(expense_date,total_amount,vat_amount,branch_id) VALUES('2026-09-07',11.50,1.50,1)")
        self.c.commit()
    def tearDown(self): self.c.close(); os.unlink(self.path)
    def test_sales_vat_and_profit(self):
        s=sales_summary(self.c,start_date='2026-09-07',end_date='2026-09-07')
        self.assertEqual(s['gross_sales'],215); self.assertEqual(s['vat'],28.04); self.assertEqual(s['cost_of_goods'],90); self.assertEqual(s['gross_profit'],125)
    def test_branch_filter(self):
        s=sales_summary(self.c,start_date='2026-09-07',end_date='2026-09-07',branch_id=2)
        self.assertEqual(s['gross_sales'],100); self.assertEqual(s['card_sales'],100); self.assertEqual(s['transactions'],1)
    def test_void_is_excluded(self):
        self.c.execute("UPDATE sales_history SET voided=1 WHERE id=2"); self.c.commit()
        s=sales_summary(self.c,start_date='2026-09-07',end_date='2026-09-07')
        self.assertEqual(s['gross_sales'],115); self.assertEqual(s['transactions'],1)
    def test_return_reduces_net_sales_and_restores_cost(self):
        self.c.execute("INSERT INTO return_history(timestamp,original_sale_id,total_amount,refund_type,cashier) VALUES('2026-09-07 12:00',1,23,'Cash Refund','alice')")
        rid=self.c.execute('SELECT last_insert_rowid()').fetchone()[0]
        self.c.execute("INSERT INTO return_items(return_id,sale_item_id,barcode,description,qty,price,value) VALUES(?,?,?,?,?,?,?)",(rid,1,'A','Item',1,23,23)); self.c.commit()
        f=financial_summary(self.c,start_date='2026-09-07',end_date='2026-09-07',branch_id=1)
        self.assertEqual(f['net_sales'],92); self.assertEqual(f['returned_cost'],10); self.assertEqual(f['cost_of_goods'],40); self.assertEqual(f['gross_profit'],52)
    def test_expenses_reduce_net_profit(self):
        f=financial_summary(self.c,start_date='2026-09-07',end_date='2026-09-07',branch_id=1)
        self.assertEqual(f['gross_profit'],65); self.assertEqual(f['expenses'],11.5); self.assertEqual(f['net_profit'],53.5)
    def test_customer_balance(self):
        self.c.executemany('INSERT INTO customer_account_transactions(customer_id,debit,credit) VALUES(?,?,?)',[(7,100,0),(7,0,25)])
        self.assertEqual(customer_balance(self.c,7),75)
    def test_supplier_balance(self):
        self.c.executemany('INSERT INTO account_transactions(account_id,txn_type,total_amount,txn_date) VALUES(?,?,?,?)',[(9,'PURCHASE',500,'2026-09-07'),(9,'PAYMENT',125,'2026-09-07')])
        self.assertEqual(supplier_balance(self.c,9),375)
    def test_branch_expense_isolated(self):
        f=financial_summary(self.c,start_date='2026-09-07',end_date='2026-09-07',branch_id=2)
        self.assertEqual(f['expenses'],0); self.assertEqual(f['net_profit'],60)

if __name__=='__main__': unittest.main()
