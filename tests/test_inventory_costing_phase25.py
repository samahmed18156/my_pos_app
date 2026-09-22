import sqlite3, unittest
from services.grn_service import post_grn
from services.sales_service import post_sale
from services.returns_service import post_return
from services.branch_stock_service import ensure_schema

class InventoryCostingPhase25Tests(unittest.TestCase):
    def setUp(self):
        self.c = sqlite3.connect(':memory:')
        self.c.executescript('''
        CREATE TABLE products(barcode TEXT PRIMARY KEY, description TEXT, selling_price REAL, cost_price REAL, soh REAL);
        CREATE TABLE branches(id INTEGER PRIMARY KEY, name TEXT); INSERT INTO branches VALUES(1,'Main');
        CREATE TABLE grn_headers(id INTEGER PRIMARY KEY AUTOINCREMENT,grn_no TEXT UNIQUE,supplier_id INTEGER,supplier_account TEXT,supplier_name TEXT,supplier_invoice TEXT,reference TEXT,vat_mode TEXT,subtotal REAL,vat REAL,total REAL,created_at TEXT,cashier TEXT,paid REAL DEFAULT 0,outstanding REAL DEFAULT 0,status TEXT DEFAULT 'UNPAID');
        CREATE TABLE grn_items(id INTEGER PRIMARY KEY AUTOINCREMENT,grn_id INTEGER,barcode TEXT,description TEXT,soh_before REAL,order_qty REAL,qty_received REAL,cost_price REAL,value REAL);
        CREATE TABLE account_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,account_id INTEGER,txn_type TEXT,total_amount REAL,txn_date TEXT);
        CREATE TABLE sales_history(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp TEXT,total_amount REAL,total_cost REAL,payment_type TEXT,cashier TEXT,customer_id INTEGER,customer_account TEXT,customer_name TEXT,branch_id INTEGER,branch_name TEXT,amount_tendered REAL,change_amount REAL,cash_amount REAL,card_amount REAL,voided INTEGER DEFAULT 0);
        CREATE TABLE sale_items(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER,barcode TEXT,description TEXT,qty REAL,price REAL,value REAL);
        CREATE TABLE return_history(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp TEXT,original_sale_id INTEGER,total_amount REAL,refund_type TEXT,cashier TEXT,reason TEXT);
        CREATE TABLE return_items(id INTEGER PRIMARY KEY AUTOINCREMENT,return_id INTEGER,sale_item_id INTEGER,barcode TEXT,description TEXT,qty REAL,price REAL,value REAL);
        CREATE TABLE stock_movements(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp TEXT,barcode TEXT,description TEXT,movement_type TEXT,qty REAL,qty_before REAL,qty_after REAL,cost_price REAL,reference TEXT,reason TEXT,cashier TEXT);
        ''')
        self.c.execute("INSERT INTO products VALUES('A','Widget',100,10,10)")
        ensure_schema(self.c); self.c.commit()

    def test_grn_uses_perpetual_weighted_average(self):
        post_grn(self.c, supplier_id=1,supplier_account='SUP',supplier_name='Supplier',items=[{'barcode':'A','qty':10,'cost':20}],vat_mode='Inclusive',grn_no='GRN-1')
        cost=self.c.execute("SELECT cost_price FROM products WHERE barcode='A'").fetchone()[0]
        self.assertAlmostEqual(cost,15.0,places=2)
        self.assertEqual(self.c.execute("SELECT soh FROM products WHERE barcode='A'").fetchone()[0],20.0)

    def test_sale_records_historical_moving_average_cost(self):
        post_grn(self.c, supplier_id=1,supplier_account='SUP',supplier_name='Supplier',items=[{'barcode':'A','qty':10,'cost':20}],vat_mode='Inclusive',grn_no='GRN-1')
        sid=post_sale(self.c,cart=[{'code':'A','name':'Widget','qty':2,'price':100,'value':200}],total=200,total_cost=999,payment_info={'cash':200},payment_type='Cash',cashier='tester')
        h=self.c.execute("SELECT total_cost FROM sales_history WHERE id=?",(sid,)).fetchone()[0]
        line=self.c.execute("SELECT cost_price FROM sale_items WHERE sale_id=?",(sid,)).fetchone()[0]
        self.assertAlmostEqual(h,30.0,places=2)
        self.assertAlmostEqual(line,15.0,places=2)

    def test_customer_return_uses_original_sale_cost(self):
        post_grn(self.c, supplier_id=1,supplier_account='SUP',supplier_name='Supplier',items=[{'barcode':'A','qty':10,'cost':20}],vat_mode='Inclusive',grn_no='GRN-1')
        sid=post_sale(self.c,cart=[{'code':'A','name':'Widget','qty':2,'price':100,'value':200}],total=200,total_cost=0,payment_info={'cash':200},payment_type='Cash',cashier='tester')
        # Buy another batch at a higher price; moving average changes to 25.
        post_grn(self.c, supplier_id=1,supplier_account='SUP',supplier_name='Supplier',items=[{'barcode':'A','qty':10,'cost':40}],vat_mode='Inclusive',grn_no='GRN-2')
        current=self.c.execute("SELECT cost_price FROM products WHERE barcode='A'").fetchone()[0]
        self.assertAlmostEqual(current,23.93,places=2)
        item_id=self.c.execute("SELECT id FROM sale_items WHERE sale_id=?",(sid,)).fetchone()[0]
        post_return(self.c,sale_id=sid,lines=[{'sale_item_id':item_id,'qty':1}],refund_type='Cash Refund',cashier='tester')
        # Returned unit re-enters at its original sale COGS (15), then average is recalculated.
        cost=self.c.execute("SELECT cost_price FROM products WHERE barcode='A'").fetchone()[0]
        self.assertAlmostEqual(cost,23.62,places=2)

if __name__=='__main__': unittest.main()
