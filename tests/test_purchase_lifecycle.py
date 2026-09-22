import os, sqlite3, tempfile, unittest

from services import branch_stock_service, grn_service, supplier_credit_service, accounts_service
from services.financial_reconciliation import supplier_balance


class PurchaseLifecycleTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix='.db'); os.close(fd)
        self.c = sqlite3.connect(self.path)
        self.c.executescript('''
        CREATE TABLE branches(id INTEGER PRIMARY KEY,name TEXT); INSERT INTO branches VALUES(1,'Main'),(2,'Branch 2');
        CREATE TABLE products(barcode TEXT PRIMARY KEY,description TEXT,cost_price REAL,selling_price REAL,soh REAL);
        INSERT INTO products VALUES('A','Widget',10,25,10),('B','Cable',5,12,3);
        CREATE TABLE branch_stock(branch_id INTEGER,barcode TEXT,soh REAL,PRIMARY KEY(branch_id,barcode));
        CREATE TABLE stock_movements(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp TEXT,barcode TEXT,description TEXT,movement_type TEXT,qty REAL,qty_before REAL,qty_after REAL,cost_price REAL,reference TEXT,reason TEXT,cashier TEXT);
        CREATE TABLE accounts(id INTEGER PRIMARY KEY,name TEXT,type TEXT,supplier_account_no TEXT,credit_limit REAL DEFAULT 0);
        CREATE TABLE account_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,account_id INTEGER,txn_type TEXT,total_amount REAL,txn_date TEXT);
        CREATE TABLE supplier_payments(id INTEGER PRIMARY KEY AUTOINCREMENT,payment_no TEXT,supplier_id INTEGER,supplier_account_no TEXT,supplier_name TEXT,payment_date TEXT,amount REAL,payment_method TEXT,reference TEXT,notes TEXT,cashier TEXT,created_by TEXT);
        CREATE TABLE supplier_credits(id INTEGER PRIMARY KEY AUTOINCREMENT,credit_no TEXT UNIQUE,supplier_id INTEGER,credit_date TEXT,amount REAL,reason TEXT,reference TEXT,created_by TEXT,stock_returned REAL DEFAULT 0,item_count INTEGER DEFAULT 0);
        CREATE TABLE supplier_credit_items(id INTEGER PRIMARY KEY AUTOINCREMENT,credit_id INTEGER,grn_id INTEGER,grn_item_id INTEGER,barcode TEXT,description TEXT,qty REAL,unit_cost REAL,value REAL,created_at TEXT);
        ''')
        self.c.execute("INSERT INTO accounts(id,name,type,supplier_account_no) VALUES(7,'Acme Supplies','Supplier','SUP-007')")
        self.c.commit()
        self.old_branch_db = branch_stock_service.DB_NAME
        branch_stock_service.DB_NAME = self.path
        branch_stock_service.ensure_schema(self.c); self.c.commit()

    def tearDown(self):
        branch_stock_service.DB_NAME = self.old_branch_db
        self.c.close(); os.unlink(self.path)

    def grn(self, **overrides):
        args = dict(supplier_id=7, supplier_account='SUP-007', supplier_name='Acme Supplies',
                    items=[{'barcode':'A','qty':5,'cost':20}], branch_id=1,
                    cashier='manager', supplier_invoice='INV-100', reference='DN-100', vat_mode='Inclusive', grn_no='GRN-000001')
        args.update(overrides)
        return grn_service.post_grn(self.c, **args)

    def test_grn_creates_purchase_document_stock_and_liability(self):
        result=self.grn(); self.c.commit()
        self.assertEqual(result['total'],100.0)
        self.assertEqual(self.c.execute("SELECT total,subtotal,vat,supplier_id FROM grn_headers").fetchone(),(100.0,86.96,13.04,7))
        self.assertEqual(self.c.execute("SELECT qty_received,cost_price,value FROM grn_items").fetchone(),(5.0,20.0,100.0))
        self.assertEqual(self.c.execute("SELECT soh FROM branch_stock WHERE branch_id=1 AND barcode='A'").fetchone()[0],15.0)
        self.assertEqual(self.c.execute("SELECT soh FROM products WHERE barcode='A'").fetchone()[0],15.0)
        self.assertEqual(supplier_balance(self.c,7),100.0)
        self.assertEqual(self.c.execute("SELECT movement_type,qty,qty_before,qty_after FROM stock_movements").fetchone(),('GRN',5.0,10.0,15.0))

    def test_grn_can_receive_into_specific_branch_without_changing_other_branch(self):
        self.grn(branch_id=2, grn_no='GRN-000002'); self.c.commit()
        b1=self.c.execute("SELECT soh FROM branch_stock WHERE branch_id=1 AND barcode='A'").fetchone()[0]
        b2=self.c.execute("SELECT soh FROM branch_stock WHERE branch_id=2 AND barcode='A'").fetchone()[0]
        global_soh=self.c.execute("SELECT soh FROM products WHERE barcode='A'").fetchone()[0]
        self.assertEqual((b1,b2,global_soh),(10.0,5.0,15.0))

    def test_grn_updates_product_cost_only_after_success(self):
        self.grn(); self.c.commit()
        self.assertAlmostEqual(self.c.execute("SELECT cost_price FROM products WHERE barcode='A'").fetchone()[0],13.33,places=2)

    def test_grn_rolls_back_if_any_item_is_invalid(self):
        with self.assertRaises(ValueError):
            self.grn(items=[{'barcode':'A','qty':2,'cost':20},{'barcode':'MISSING','qty':1,'cost':5}])
        self.c.rollback()
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM grn_headers").fetchone()[0],0)
        self.assertEqual(self.c.execute("SELECT soh FROM products WHERE barcode='A'").fetchone()[0],10.0)
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM stock_movements").fetchone()[0],0)

    def test_supplier_credit_reduces_stock_and_liability_against_exact_grn_item(self):
        self.grn(); self.c.commit()
        gi=self.c.execute("SELECT id FROM grn_items").fetchone()[0]
        result=supplier_credit_service.post_supplier_stock_credit(self.c,supplier_id=7,items=[{'grn_item_id':gi,'qty':2}],branch_id=1,credit_no='SCN-1',created_by='manager')
        self.c.commit()
        self.assertEqual(result['amount'],40.0)
        self.assertEqual(self.c.execute("SELECT soh FROM branch_stock WHERE branch_id=1 AND barcode='A'").fetchone()[0],13.0)
        self.assertEqual(self.c.execute("SELECT soh FROM products WHERE barcode='A'").fetchone()[0],13.0)
        self.assertEqual(supplier_balance(self.c,7),60.0)
        self.assertEqual(self.c.execute("SELECT qty,value FROM supplier_credit_items").fetchone(),(2.0,40.0))

    def test_supplier_credit_cannot_exceed_remaining_grn_quantity(self):
        self.grn(); self.c.commit(); gi=self.c.execute("SELECT id FROM grn_items").fetchone()[0]
        supplier_credit_service.post_supplier_stock_credit(self.c,supplier_id=7,items=[{'grn_item_id':gi,'qty':4}],branch_id=1,credit_no='SCN-1',created_by='manager'); self.c.commit()
        with self.assertRaises(ValueError):
            supplier_credit_service.post_supplier_stock_credit(self.c,supplier_id=7,items=[{'grn_item_id':gi,'qty':2}],branch_id=1,credit_no='SCN-2',created_by='manager')
        self.c.rollback()
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM supplier_credits").fetchone()[0],1)
        self.assertEqual(self.c.execute("SELECT soh FROM products WHERE barcode='A'").fetchone()[0],11.0)

    def test_supplier_credit_cannot_create_negative_branch_stock(self):
        self.grn(); self.c.commit(); gi=self.c.execute("SELECT id FROM grn_items").fetchone()[0]
        with self.assertRaises(ValueError):
            supplier_credit_service.post_supplier_stock_credit(self.c,supplier_id=7,items=[{'grn_item_id':gi,'qty':6}],branch_id=1,credit_no='SCN-1')
        self.c.rollback()
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM supplier_credits").fetchone()[0],0)
        self.assertEqual(self.c.execute("SELECT soh FROM products WHERE barcode='A'").fetchone()[0],15.0)

    def test_supplier_payment_reconciles_after_grn_and_credit(self):
        self.grn(); self.c.commit(); gi=self.c.execute("SELECT id FROM grn_items").fetchone()[0]
        supplier_credit_service.post_supplier_stock_credit(self.c,supplier_id=7,items=[{'grn_item_id':gi,'qty':1}],branch_id=1,credit_no='SCN-1',created_by='manager')
        accounts_service.supplier_payment(self.c,supplier_id=7,amount=30,reference='PAY-1',cashier='manager')
        self.c.commit()
        self.assertEqual(supplier_balance(self.c,7),50.0)
        self.assertEqual(self.c.execute("SELECT amount FROM supplier_payments").fetchone()[0],30.0)

    def test_supplier_payment_cannot_exceed_liability(self):
        self.grn(); self.c.commit()
        with self.assertRaises(ValueError): accounts_service.supplier_payment(self.c,supplier_id=7,amount=101,reference='PAY-OVER')
        self.c.rollback()
        self.assertEqual(self.c.execute("SELECT COUNT(*) FROM supplier_payments").fetchone()[0],0)


if __name__ == '__main__': unittest.main()
