import sqlite3, tempfile, os, unittest
from supplier_inventory_optimization import supplier_performance,cost_variance,reorder_suggestions,dead_stock
class Phase7Tests(unittest.TestCase):
 def setUp(self):
  f=tempfile.NamedTemporaryFile(delete=False,suffix='.db'); f.close(); self.path=f.name; c=sqlite3.connect(self.path); c.executescript('''
  CREATE TABLE grn_headers(id INTEGER PRIMARY KEY, supplier_id INTEGER,supplier_name TEXT,total REAL,outstanding REAL,created_at TEXT);
  CREATE TABLE grn_items(id INTEGER PRIMARY KEY,grn_id INTEGER,barcode TEXT,description TEXT,qty_received REAL,cost_price REAL,value REAL);
  CREATE TABLE products(barcode TEXT PRIMARY KEY,description TEXT,selling_price REAL,cost_price REAL,soh REAL,min_stock REAL,reorder_qty REAL,active INTEGER,category TEXT);
  CREATE TABLE sales_history(id INTEGER PRIMARY KEY,timestamp TEXT,voided INTEGER,status TEXT,total_amount REAL);
  CREATE TABLE sale_items(id INTEGER PRIMARY KEY,sale_id INTEGER,barcode TEXT,qty REAL,price REAL);
  INSERT INTO grn_headers VALUES(1,1,'Supplier A',100,60,'2026-09-01 10:00');
  INSERT INTO grn_items VALUES(1,1,'A','Fast',10,10,100);
  INSERT INTO products VALUES('A','Fast',15,12,2,5,4,1,'Food');
  INSERT INTO products VALUES('B','Dead',20,8,10,2,0,1,'Other');
  INSERT INTO sales_history VALUES(1,'2026-09-02 10:00',0,'COMPLETED',150);
  INSERT INTO sale_items VALUES(1,1,'A',3,15);
  '''); c.commit(); c.close()
 def tearDown(self): os.unlink(self.path)
 def conn(self): return sqlite3.connect(self.path)
 def test_supplier_performance(self):
  c=self.conn(); r=supplier_performance(c,'2026-09-01','2026-09-02'); c.close(); self.assertEqual(r[0][0],'Supplier A'); self.assertEqual(r[0][1],1); self.assertEqual(r[0][2],100)
 def test_cost_variance(self):
  c=self.conn(); r=cost_variance(c,'2026-09-01','2026-09-02'); c.close(); self.assertEqual(r[0][0],'A'); self.assertEqual(r[0][3],10)
 def test_reorder_uses_demand_and_minimum(self):
  c=self.conn(); r=reorder_suggestions(c,'2026-09-01','2026-09-02'); c.close(); a=next(x for x in r if x[0]=='A'); self.assertGreater(a[6],0)
 def test_dead_stock(self):
  c=self.conn(); r=dead_stock(c,'2026-09-02','2026-09-02',60); c.close(); self.assertEqual(r[0][0],'B'); self.assertEqual(r[0][6],80)
if __name__=='__main__': unittest.main()
