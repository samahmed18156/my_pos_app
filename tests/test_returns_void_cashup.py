import os, sqlite3, tempfile, unittest

from services.branch_stock_service import ensure_schema, transfer
from services.sales_service import post_sale
from services.returns_service import post_return
from services.financial_service import void_sale, cashup_summary


class ReturnsVoidCashupTests(unittest.TestCase):
    def setUp(self):
        f = tempfile.NamedTemporaryFile(delete=False); f.close(); self.path=f.name
        self.c=sqlite3.connect(self.path)
        self.c.executescript('''
        CREATE TABLE products(barcode TEXT PRIMARY KEY,description TEXT,selling_price REAL,cost_price REAL,soh REAL);
        CREATE TABLE branches(id INTEGER PRIMARY KEY,name TEXT);
        INSERT INTO branches VALUES(1,'Main Store'),(2,'Branch 2');
        CREATE TABLE branch_stock(branch_id INTEGER,barcode TEXT,soh REAL,PRIMARY KEY(branch_id,barcode));
        CREATE TABLE stock_movements(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,barcode TEXT,description TEXT,movement_type TEXT,qty REAL,qty_before REAL,qty_after REAL,cost_price REAL,reference TEXT,reason TEXT,cashier TEXT);
        CREATE TABLE stock_transfers(id INTEGER PRIMARY KEY AUTOINCREMENT,transfer_no TEXT,from_branch INTEGER,to_branch INTEGER,barcode TEXT,description TEXT,qty REAL,status TEXT DEFAULT 'POSTED',cashier TEXT,timestamp DATETIME DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE sales_history(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,total_amount REAL,total_cost REAL,payment_type TEXT,cashier TEXT,customer_id INTEGER,customer_account TEXT,customer_name TEXT,branch_id INTEGER,branch_name TEXT,amount_tendered REAL,change_amount REAL,cash_amount REAL,card_amount REAL,voided INTEGER DEFAULT 0,voided_at DATETIME,voided_by TEXT);
        CREATE TABLE sale_items(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER,barcode TEXT,description TEXT,qty REAL,price REAL,value REAL);
        CREATE TABLE return_history(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,original_sale_id INTEGER,total_amount REAL,refund_type TEXT,cashier TEXT,reason TEXT);
        CREATE TABLE return_items(id INTEGER PRIMARY KEY AUTOINCREMENT,return_id INTEGER,sale_item_id INTEGER,barcode TEXT,description TEXT,qty REAL,price REAL,value REAL);
        CREATE TABLE void_history(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,amount REAL,cash_amount REAL,card_amount REAL,cashier TEXT,reason TEXT);
        CREATE TABLE transaction_controls(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,control_type TEXT,reference TEXT,amount REAL,status TEXT,notes TEXT,cashier TEXT);
        INSERT INTO products VALUES('100','Coffee',20,10,10);
        ''')
        ensure_schema(self.c); self.c.commit()

    def tearDown(self): self.c.close(); os.unlink(self.path)

    def sale(self, **kw):
        qty=kw.pop('qty',2); total=round(qty*20,2); return post_sale(self.c, cart=[{'code':'100','name':'Coffee','qty':qty,'price':20,'value':total}], total=total,total_cost=round(qty*10,2),payment_info={'cash':total,'amount_tendered':total,'change':0},payment_type='Cash',cashier='alice',branch_id=kw.pop('branch_id',1),branch_name='Main Store')

    def test_partial_return_restores_stock_and_records_refund(self):
        sid=self.sale(); self.c.commit()
        item=self.c.execute('SELECT id FROM sale_items WHERE sale_id=?',(sid,)).fetchone()[0]
        rid,total=post_return(self.c,sale_id=sid,lines=[{'sale_item_id':item,'qty':1}],refund_type='Cash Refund',cashier='alice',branch_id=1)
        self.c.commit()
        self.assertEqual(total,20.0); self.assertEqual(self.c.execute("SELECT soh FROM branch_stock WHERE branch_id=1 AND barcode='100'").fetchone()[0],9.0)
        self.assertEqual(self.c.execute("SELECT qty FROM stock_movements WHERE movement_type='RETURN'").fetchone()[0],1.0)
        self.assertEqual(self.c.execute('SELECT total_amount FROM return_history WHERE id=?',(rid,)).fetchone()[0],20.0)

    def test_return_cannot_exceed_remaining(self):
        sid=self.sale(); self.c.commit(); item=self.c.execute('SELECT id FROM sale_items WHERE sale_id=?',(sid,)).fetchone()[0]
        post_return(self.c,sale_id=sid,lines=[{'sale_item_id':item,'qty':1}],cashier='alice',branch_id=1); self.c.commit()
        with self.assertRaises(ValueError): post_return(self.c,sale_id=sid,lines=[{'sale_item_id':item,'qty':2}],cashier='alice',branch_id=1)

    def test_return_rolls_back_stock_and_header_on_failure(self):
        sid=self.sale(); self.c.commit(); item=self.c.execute('SELECT id FROM sale_items WHERE sale_id=?',(sid,)).fetchone()[0]
        self.c.execute('DELETE FROM products WHERE barcode="100"'); self.c.commit()
        with self.assertRaises(ValueError): post_return(self.c,sale_id=sid,lines=[{'sale_item_id':item,'qty':1}],cashier='alice',branch_id=2)
        self.c.rollback()
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM return_history').fetchone()[0],0)

    def test_void_restores_only_unreturned_quantity(self):
        sid=self.sale(); self.c.commit(); item=self.c.execute('SELECT id FROM sale_items WHERE sale_id=?',(sid,)).fetchone()[0]
        post_return(self.c,sale_id=sid,lines=[{'sale_item_id':item,'qty':1}],cashier='alice',branch_id=1); self.c.commit()
        result=void_sale(self.c,sid,actor='manager',reason='Correction'); self.c.commit()
        self.assertEqual(result['restored_qty'],1.0)
        self.assertEqual(self.c.execute("SELECT soh FROM branch_stock WHERE branch_id=1 AND barcode='100'").fetchone()[0],10.0)
        self.assertEqual(self.c.execute('SELECT voided FROM sales_history WHERE id=?',(sid,)).fetchone()[0],1)
        self.assertEqual(self.c.execute("SELECT qty FROM stock_movements WHERE movement_type='VOID'").fetchone()[0],1.0)

    def test_void_is_idempotent_protected(self):
        sid=self.sale(); self.c.commit(); void_sale(self.c,sid,actor='manager'); self.c.commit()
        with self.assertRaises(ValueError): void_sale(self.c,sid,actor='manager')

    def test_void_uses_original_sale_branch(self):
        transfer(self.c,1,2,'100',4,'alice'); self.c.commit()
        sid=self.sale(branch_id=2); self.c.commit()
        void_sale(self.c,sid,actor='manager'); self.c.commit()
        self.assertEqual(self.c.execute("SELECT soh FROM branch_stock WHERE branch_id=2 AND barcode='100'").fetchone()[0],4.0)
        self.assertEqual(self.c.execute("SELECT soh FROM branch_stock WHERE branch_id=1 AND barcode='100'").fetchone()[0],6.0)

    def test_cashup_summary_excludes_void_and_subtracts_cash_refund(self):
        sid=self.sale(); self.c.commit(); item=self.c.execute('SELECT id FROM sale_items WHERE sale_id=?',(sid,)).fetchone()[0]
        post_return(self.c,sale_id=sid,lines=[{'sale_item_id':item,'qty':1}],refund_type='Cash Refund',cashier='alice',branch_id=1); self.c.commit()
        self.sale(qty=1); self.c.commit(); sid2=self.c.execute('SELECT max(id) FROM sales_history').fetchone()[0]
        void_sale(self.c,sid2,actor='manager'); self.c.commit()
        s=cashup_summary(self.c,date=__import__('datetime').datetime.now().strftime('%Y-%m-%d'),cashier='alice',opening_float=100)
        self.assertEqual(s['gross_sales'],40.0)
        s=cashup_summary(self.c,date=__import__('datetime').datetime.now().strftime('%Y-%m-%d'),cashier='alice',opening_float=100)
        self.assertEqual(s['expected_cash'],120.0)


if __name__=='__main__': unittest.main()
