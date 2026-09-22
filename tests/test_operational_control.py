import os, sqlite3, tempfile, unittest
from unittest.mock import patch

class OperationalControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.NamedTemporaryFile(delete=False,suffix='.db'); self.tmp.close()
        c=sqlite3.connect(self.tmp.name)
        c.executescript('''
        CREATE TABLE sales_history(id INTEGER PRIMARY KEY,timestamp TEXT,total_amount REAL,total_cost REAL,voided INTEGER DEFAULT 0,status TEXT DEFAULT 'COMPLETED',cashier TEXT,branch_id INTEGER);
        CREATE TABLE sale_items(id INTEGER PRIMARY KEY,sale_id INTEGER,barcode TEXT,description TEXT,qty REAL,price REAL,value REAL,cost_price REAL DEFAULT 0);
        CREATE TABLE products(barcode TEXT PRIMARY KEY,description TEXT,selling_price REAL,cost_price REAL,soh REAL DEFAULT 0,min_stock REAL DEFAULT 5,active INTEGER DEFAULT 1,category TEXT DEFAULT '');
        INSERT INTO sales_history VALUES(1,'2026-09-01 10:00',100,60,0,'COMPLETED','A',1);
        INSERT INTO sales_history VALUES(2,'2026-09-02 10:00',200,120,0,'COMPLETED','B',1);
        INSERT INTO sales_history VALUES(3,'2026-09-02 11:00',999,500,1,'VOID','B',1);
        INSERT INTO sale_items VALUES(1,1,'A','Fast',10,10,100,6);
        INSERT INTO sale_items VALUES(2,2,'B','Slow',1,200,200,120);
        INSERT INTO products VALUES('A','Fast',10,6,2,5,1,'Food');
        INSERT INTO products VALUES('B','Slow',200,120,20,5,1,'Other');
        '''); c.commit(); c.close()
    def tearDown(self): os.unlink(self.tmp.name)
    def test_summary_excludes_void(self):
        with patch('operational_control.DB_PATH',self.tmp.name):
            from operational_control import performance_summary
            c=sqlite3.connect(self.tmp.name); r=performance_summary(c,'2026-09-01','2026-09-02',150); c.close()
        self.assertEqual(r['sales'],300.0); self.assertEqual(r['transactions'],2); self.assertEqual(r['target'],300.0); self.assertEqual(r['variance'],0.0)
    def test_reorder_recommends_fast_product(self):
        with patch('operational_control.DB_PATH',self.tmp.name):
            from operational_control import stock_intelligence
            c=sqlite3.connect(self.tmp.name); rows=stock_intelligence(c,'2026-09-01','2026-09-02'); c.close()
        fast=next(r for r in rows if r[1]=='A'); self.assertGreater(fast[6],0); self.assertIn('REORDER',fast[7])
    def test_category_performance(self):
        with patch('operational_control.DB_PATH',self.tmp.name):
            from operational_control import category_performance
            c=sqlite3.connect(self.tmp.name); rows=category_performance(c,'2026-09-01','2026-09-02'); c.close()
        food=next(r for r in rows if r[0]=='Food'); self.assertEqual(food[1],10); self.assertEqual(food[2],100.0)

if __name__=='__main__': unittest.main()
