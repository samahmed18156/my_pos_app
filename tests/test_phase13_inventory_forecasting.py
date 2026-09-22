import sqlite3
from inventory_forecasting import demand_forecast, seasonality

def db():
 c=sqlite3.connect(':memory:'); c.executescript('''
 CREATE TABLE products(barcode TEXT PRIMARY KEY,description TEXT,category TEXT,soh REAL,cost_price REAL,min_stock REAL,active INTEGER);
 CREATE TABLE sales_history(id INTEGER PRIMARY KEY,timestamp TEXT,voided INTEGER,status TEXT);
 CREATE TABLE sale_items(id INTEGER PRIMARY KEY,sale_id INTEGER,barcode TEXT,qty REAL);
 INSERT INTO products VALUES('A','Milk','Dairy',10,8,5,1);
 INSERT INTO sales_history VALUES(1,'2026-09-01 10:00',0,'COMPLETED');
 INSERT INTO sales_history VALUES(2,'2026-09-09 10:00',0,'COMPLETED');
 INSERT INTO sale_items VALUES(1,1,'A',4); INSERT INTO sale_items VALUES(2,2,'A',6);
 '''); return c

def test_forecast_weighted_and_risk():
 c=db(); r=demand_forecast(c,'2026-09-01','2026-09-10',30)[0]; assert r[0]=='A'; assert r[7]>0; assert r[10] in {'STOCKOUT','WATCH','OK'}

def test_voids_and_status_excluded():
 c=db(); c.execute("INSERT INTO sales_history VALUES(3,'2026-09-10 10:00',1,'COMPLETED')"); c.execute("INSERT INTO sale_items VALUES(3,3,'A',100)"); r=demand_forecast(c,'2026-09-01','2026-09-10')[0]; assert r[5] < 2

def test_seasonality():
 c=db(); r=seasonality(c,'2026-09-01','2026-09-10'); assert r and r[0][0]=='A'
