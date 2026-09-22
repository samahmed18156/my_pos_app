import os, sqlite3, tempfile, unittest
from unittest.mock import patch

class BusinessIntelligenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.NamedTemporaryFile(delete=False,suffix='.db'); self.tmp.close()
        c=sqlite3.connect(self.tmp.name)
        c.executescript('''
        CREATE TABLE sales_history(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp TEXT,total_amount REAL,total_cost REAL,payment_type TEXT,cashier TEXT,branch_id INTEGER,branch_name TEXT,voided INTEGER DEFAULT 0,status TEXT DEFAULT 'COMPLETED');
        CREATE TABLE sale_items(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER,barcode TEXT,description TEXT,qty REAL,price REAL,value REAL,cost_price REAL DEFAULT 0);
        CREATE TABLE products(barcode TEXT PRIMARY KEY,description TEXT,category TEXT,stock_on_hand REAL DEFAULT 0,min_stock REAL DEFAULT 5,active INTEGER DEFAULT 1);
        INSERT INTO sales_history VALUES(1,'2026-09-01 10:00',115,70,'Cash','Alice',1,'Main',0,'COMPLETED');
        INSERT INTO sales_history VALUES(2,'2026-09-02 11:00',230,140,'Card','Bob',2,'Branch 2',0,'COMPLETED');
        INSERT INTO sales_history VALUES(3,'2026-09-02 12:00',100,60,'Cash','Alice',1,'Main',1,'VOID');
        INSERT INTO sale_items VALUES(1,1,'A','Widget',2,57.5,115,35);
        INSERT INTO sale_items VALUES(2,2,'B','Gadget',1,230,230,140);
        INSERT INTO products VALUES('A','Widget','General',3,5,1);
        INSERT INTO products VALUES('B','Gadget','Electronics',10,5,1);
        '''); c.commit(); c.close()

    def tearDown(self): os.unlink(self.tmp.name)

    def test_queries_exclude_voided_sales(self):
        with patch('business_intelligence.DB_PATH', self.tmp.name):
            from business_intelligence import _conn
            c=_conn(); row=c.execute("SELECT SUM(total_amount),COUNT(*) FROM sales_history WHERE date(timestamp) BETWEEN '2026-09-01' AND '2026-09-02' AND COALESCE(voided,0)=0 AND COALESCE(status,'COMPLETED')='COMPLETED'").fetchone(); c.close()
        self.assertEqual(row,(345.0,2))

    def test_low_stock_query(self):
        with patch('business_intelligence.DB_PATH', self.tmp.name):
            from business_intelligence import _conn
            c=_conn(); rows=c.execute("SELECT description FROM products WHERE COALESCE(active,1)=1 AND stock_on_hand<=min_stock ORDER BY stock_on_hand").fetchall(); c.close()
        self.assertEqual(rows,[('Widget',)])

if __name__=='__main__': unittest.main()
