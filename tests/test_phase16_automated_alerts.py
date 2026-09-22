import sqlite3
from automated_alerts import ensure_schema,generate_alerts,list_alerts,acknowledge_alert,alert_summary

def db():
 c=sqlite3.connect(':memory:')
 c.executescript('''CREATE TABLE products(id INTEGER PRIMARY KEY,description TEXT,soh REAL,min_stock REAL);
 INSERT INTO products VALUES(1,'Milk',-2,1),(2,'Bread',1,3),(3,'Coffee',20,2);
 CREATE TABLE cashier_shifts(id INTEGER PRIMARY KEY,cashier TEXT,status TEXT,difference REAL);
 INSERT INTO cashier_shifts VALUES(1,'Alice','OPEN',0),(2,'Bob','CLOSED',25);
 CREATE TABLE sales_history(id INTEGER PRIMARY KEY,timestamp TEXT,total_amount REAL,voided INTEGER);
 INSERT INTO sales_history VALUES(1,'2026-09-10 08:00',100,1);
 CREATE TABLE staged_conflicts(id INTEGER PRIMARY KEY); INSERT INTO staged_conflicts VALUES(1);''')
 ensure_schema(c);return c

def test_generate_and_summary():
 c=db(); a=generate_alerts(c,'2026-09-10'); assert len(a)>=5; s=alert_summary(c); assert s['high']>=3; assert s['inventory']>=2

def test_idempotent():
 c=db(); generate_alerts(c,'2026-09-10'); n=len(list_alerts(c)); generate_alerts(c,'2026-09-10'); assert len(list_alerts(c))==n

def test_acknowledge():
 c=db();generate_alerts(c,'2026-09-10');aid=list_alerts(c)[0][0];acknowledge_alert(aid,c);assert aid not in [r[0] for r in list_alerts(c)]
