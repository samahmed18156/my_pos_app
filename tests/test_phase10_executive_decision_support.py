import os, sqlite3, tempfile, unittest
from executive_decision_support import previous_period, executive_summary, branch_performance, product_performance, decision_alerts

class Phase10Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.NamedTemporaryFile(delete=False,suffix='.db'); self.tmp.close()
        c=sqlite3.connect(self.tmp.name)
        c.executescript('''
        CREATE TABLE sales_history(id INTEGER PRIMARY KEY,timestamp TEXT,total_amount REAL,total_cost REAL,payment_type TEXT,cashier TEXT,branch_id INTEGER,branch_name TEXT,voided INTEGER DEFAULT 0,status TEXT DEFAULT 'COMPLETED');
        CREATE TABLE sale_items(id INTEGER PRIMARY KEY,sale_id INTEGER,barcode TEXT,description TEXT,qty REAL,price REAL,value REAL,cost_price REAL DEFAULT 0);
        CREATE TABLE products(barcode TEXT PRIMARY KEY,description TEXT,category TEXT,soh REAL DEFAULT 0,min_stock REAL DEFAULT 5,active INTEGER DEFAULT 1,cost_price REAL DEFAULT 0);
        INSERT INTO sales_history VALUES(1,'2026-09-10 10:00',200,120,'Cash','A',1,'Main',0,'COMPLETED');
        INSERT INTO sales_history VALUES(2,'2026-09-09 10:00',100,60,'Card','B',2,'North',0,'COMPLETED');
        INSERT INTO sales_history VALUES(3,'2026-09-08 10:00',150,90,'Cash','A',1,'Main',0,'COMPLETED');
        INSERT INTO sales_history VALUES(4,'2026-09-10 11:00',999,500,'Cash','A',1,'Main',1,'VOID');
        INSERT INTO sale_items VALUES(1,1,'A','Milk',4,50,200,30);
        INSERT INTO sale_items VALUES(2,2,'B','Bread',2,50,100,30);
        INSERT INTO products VALUES('A','Milk','Grocery',4,5,1,30);
        INSERT INTO products VALUES('B','Bread','Bakery',10,5,1,30);
        INSERT INTO products VALUES('C','Rice','Grocery',8,5,1,30);
        '''); c.commit(); self.c=c
    def tearDown(self): self.c.close(); os.unlink(self.tmp.name)
    def test_previous_period(self): self.assertEqual(previous_period('2026-09-10','2026-09-10'),('2026-09-09','2026-09-09'))
    def test_summary_excludes_voids_and_compares(self):
        s=executive_summary(self.c,'2026-09-09','2026-09-10'); self.assertEqual(s['sales'],300); self.assertEqual(s['transactions'],2); self.assertEqual(s['previous_sales'],150); self.assertAlmostEqual(s['growth_pct'],100)
    def test_branch_and_product_performance(self):
        b=branch_performance(self.c,'2026-09-09','2026-09-10'); self.assertEqual(b[0][1],'Main'); self.assertEqual(b[0][3],200)
        p=product_performance(self.c,'2026-09-09','2026-09-10'); self.assertEqual(p[0][1],'Milk'); self.assertEqual(p[0][2],4)
    def test_alerts_are_actionable(self):
        a=decision_alerts(self.c,'2026-09-09','2026-09-10'); self.assertTrue(any(x[1]=='Reorder pressure' for x in a)); self.assertTrue(any(x[1]=='Unsold inventory' for x in a))

if __name__=='__main__': unittest.main()
