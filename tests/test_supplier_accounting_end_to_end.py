import os, sqlite3, tempfile, unittest
from services import grn_service, supplier_credit_service, accounts_service
from services.financial_reconciliation import supplier_balance

class SupplierAccountingEndToEndTests(unittest.TestCase):
    def setUp(self):
        fd,self.path=tempfile.mkstemp(suffix='.db'); os.close(fd)
        self.c=sqlite3.connect(self.path)
        self.c.executescript('''
        CREATE TABLE products(barcode TEXT PRIMARY KEY,description TEXT,cost_price REAL,selling_price REAL,soh REAL);
        INSERT INTO products VALUES('A','Widget',10,25,20);
        CREATE TABLE branches(id INTEGER PRIMARY KEY,name TEXT); INSERT INTO branches VALUES(1,'Main');
        CREATE TABLE branch_stock(branch_id INTEGER,barcode TEXT,soh REAL,PRIMARY KEY(branch_id,barcode));
        INSERT INTO branch_stock VALUES(1,'A',20);
        CREATE TABLE stock_movements(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp TEXT,barcode TEXT,description TEXT,movement_type TEXT,qty REAL,qty_before REAL,qty_after REAL,cost_price REAL,reference TEXT,reason TEXT,cashier TEXT);
        CREATE TABLE accounts(id INTEGER PRIMARY KEY,name TEXT,type TEXT,supplier_account_no TEXT);
        INSERT INTO accounts VALUES(7,'Acme','Supplier','SUP-007');
        CREATE TABLE account_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,account_id INTEGER,txn_type TEXT,total_amount REAL,txn_date TEXT);
        CREATE TABLE supplier_payments(id INTEGER PRIMARY KEY AUTOINCREMENT,payment_no TEXT,supplier_id INTEGER,supplier_account_no TEXT,supplier_name TEXT,payment_date TEXT,amount REAL,payment_method TEXT,reference TEXT,notes TEXT,cashier TEXT,created_by TEXT);
        CREATE TABLE supplier_credits(id INTEGER PRIMARY KEY AUTOINCREMENT,credit_no TEXT UNIQUE,supplier_id INTEGER,credit_date TEXT,amount REAL,reason TEXT,reference TEXT,created_by TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP,stock_returned REAL DEFAULT 0,item_count INTEGER DEFAULT 0);
        CREATE TABLE supplier_credit_items(id INTEGER PRIMARY KEY AUTOINCREMENT,credit_id INTEGER,grn_id INTEGER,grn_item_id INTEGER,barcode TEXT,description TEXT,qty REAL,unit_cost REAL,value REAL,created_at TEXT);
        ''')
        self.c.commit()
    def tearDown(self): self.c.close(); os.unlink(self.path)
    def grn(self,no,cost=20,qty=5):
        return grn_service.post_grn(self.c,supplier_id=7,supplier_account='SUP-007',supplier_name='Acme',items=[{'barcode':'A','qty':qty,'cost':cost}],branch_id=1,grn_no=no,cashier='manager')
    def test_full_supplier_lifecycle_with_fifo_payment_and_credit(self):
        self.grn('GRN-1'); self.grn('GRN-2',cost=30,qty=2); self.c.commit()
        rows=self.c.execute('SELECT id,total,paid,outstanding,status FROM grn_headers ORDER BY id').fetchall()
        self.assertEqual([(r[1],r[2],r[3],r[4]) for r in rows],[(100.0,0.0,100.0,'UNPAID'),(60.0,0.0,60.0,'UNPAID')])
        accounts_service.supplier_payment(self.c,supplier_id=7,amount=120,reference='PAY-1',cashier='manager')
        self.c.commit()
        rows=self.c.execute('SELECT total,paid,outstanding,status FROM grn_headers ORDER BY id').fetchall()
        self.assertEqual([(r[0],r[1],r[2],r[3]) for r in rows],[(100.0,100.0,0.0,'PAID'),(60.0,20.0,40.0,'PART PAID')])
        gi=self.c.execute('SELECT id FROM grn_items WHERE grn_id=2').fetchone()[0]
        supplier_credit_service.post_supplier_stock_credit(self.c,supplier_id=7,items=[{'grn_item_id':gi,'qty':1}],branch_id=1,credit_no='SCN-1',created_by='manager')
        self.c.commit()
        self.assertEqual(self.c.execute('SELECT outstanding,total,status FROM grn_headers WHERE id=2').fetchone(),(10.0,60.0,'PART PAID'))
        self.assertEqual(supplier_balance(self.c,7),10.0)
        self.assertEqual(self.c.execute('SELECT soh FROM branch_stock WHERE branch_id=1 AND barcode="A"').fetchone()[0],26.0)
    def test_supplier_payment_rolls_back_without_partial_allocation(self):
        self.grn('GRN-1'); self.c.commit()
        with self.assertRaises(ValueError):
            accounts_service.supplier_payment(self.c,supplier_id=7,amount=101,reference='BAD')
        self.c.rollback()
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM supplier_payments').fetchone()[0],0)
        self.assertEqual(self.c.execute('SELECT paid,outstanding FROM grn_headers').fetchone(),(0.0,100.0))

if __name__=='__main__': unittest.main()
