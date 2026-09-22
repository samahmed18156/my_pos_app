import sqlite3
from advanced_pricing import ensure_schema, pricing_catalog, save_price_schedule, scheduled_prices, promotion_conflicts, margin_alerts

def db():
 c=sqlite3.connect(':memory:')
 c.executescript('''CREATE TABLE products(id INTEGER PRIMARY KEY,description TEXT,selling_price REAL,cost_price REAL);
 CREATE TABLE promotions(id INTEGER PRIMARY KEY,name TEXT,promo_type TEXT,value REAL,start_date TEXT,end_date TEXT,min_spend REAL,active INTEGER,notes TEXT);
 INSERT INTO products VALUES(1,'Milk',20,15),(2,'Bread',10,9),(3,'Coffee',100,60);
 INSERT INTO promotions VALUES(1,'Weekend','Percentage',10,'2026-09-01','2026-09-15',0,1,''),(2,'Clearance','Fixed Amount',5,'2026-09-10','2026-09-20',0,1,'');''')
 ensure_schema(c); return c

def test_catalog_and_margin_alerts():
 c=db(); rows=pricing_catalog(c); assert rows[0][0]==2 or rows[0][0]==3 or rows[0][0]==1; assert any(r[0]==2 for r in margin_alerts(c,15))

def test_schedule_and_min_margin():
 c=db(); save_price_schedule(1,18,'2026-10-01','',None,10,'markup',conn=c); r=scheduled_prices(c); assert r[0][1]==1 and r[0][4]==18

def test_schedule_rejects_margin():
 c=db()
 try:
  save_price_schedule(2,9.5,'2026-10-01','',None,10,'bad',conn=c)
 except ValueError:
  pass
 else:
  raise AssertionError('margin protection did not reject')

def test_promotion_overlap():
 c=db(); assert len(promotion_conflicts(c))==1
