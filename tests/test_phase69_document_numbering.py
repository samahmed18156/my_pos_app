import sqlite3, unittest
from core.document_numbers import next_document_number
from core.schema_manager import migrate_connection
from services.sales_service import post_sale

class Phase69Tests(unittest.TestCase):
    def test_schema_v4_and_sequences(self):
        c=sqlite3.connect(':memory:')
        c.executescript('''CREATE TABLE branches(id INTEGER PRIMARY KEY,name TEXT); INSERT INTO branches VALUES(1,'Main'); CREATE TABLE sales_history(id INTEGER PRIMARY KEY AUTOINCREMENT,total_amount REAL); CREATE TABLE grn_headers(id INTEGER PRIMARY KEY AUTOINCREMENT,grn_no TEXT); CREATE TABLE return_history(id INTEGER PRIMARY KEY AUTOINCREMENT,total_amount REAL); CREATE TABLE supplier_credits(id INTEGER PRIMARY KEY AUTOINCREMENT,credit_no TEXT);''')
        self.assertEqual(migrate_connection(c),5)
        c.execute("INSERT INTO sales_history(total_amount,sale_no) VALUES(1,'INV-000123')")
        c.commit()
        self.assertEqual(next_document_number(c,'sale','INV'),'INV-000002')
        self.assertEqual(next_document_number(c,'return','CN'),'CN-000001')
        c.close()

    def test_sale_transaction_uid_is_idempotent(self):
        c=sqlite3.connect(':memory:')
        c.executescript('''CREATE TABLE branches(id INTEGER PRIMARY KEY,name TEXT); INSERT INTO branches VALUES(1,'Main'); CREATE TABLE sales_history(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp TEXT,total_amount REAL,total_cost REAL,payment_type TEXT,cashier TEXT,customer_id INTEGER,customer_account TEXT,customer_name TEXT,branch_id INTEGER,branch_name TEXT,amount_tendered REAL,change_amount REAL,cash_amount REAL,card_amount REAL); CREATE TABLE products(id INTEGER PRIMARY KEY,barcode TEXT UNIQUE,description TEXT,soh REAL,cost_price REAL); CREATE TABLE branch_stock(branch_id INTEGER,barcode TEXT,soh REAL,PRIMARY KEY(branch_id,barcode)); CREATE TABLE stock_movements(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp TEXT,barcode TEXT,description TEXT,movement_type TEXT,qty REAL,qty_before REAL,qty_after REAL,cost_price REAL,reference TEXT,reason TEXT,cashier TEXT);''')
        c.execute("INSERT INTO products VALUES(1,'A','Item',10,5)"); c.execute("INSERT INTO branch_stock VALUES(1,'A',10)")
        sid1=post_sale(c,cart=[{'code':'A','name':'Item','qty':1,'price':10}],total=10,total_cost=5,payment_info={'cash':10},payment_type='Cash',transaction_uid='u1')
        sid2=post_sale(c,cart=[{'code':'A','name':'Item','qty':1,'price':10}],total=10,total_cost=5,payment_info={'cash':10},payment_type='Cash',transaction_uid='u1')
        self.assertEqual(sid1,sid2); self.assertEqual(c.execute('SELECT COUNT(*) FROM sales_history').fetchone()[0],1); self.assertEqual(c.execute("SELECT soh FROM products WHERE barcode='A'").fetchone()[0],9)
        self.assertEqual(c.execute("SELECT sale_no FROM sales_history WHERE id=?",(sid1,)).fetchone()[0],'INV-000001')

if __name__=='__main__': unittest.main()
