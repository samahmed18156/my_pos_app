import sqlite3
from price_scenario_simulator import scenario_rows

def db():
    c=sqlite3.connect(':memory:')
    c.executescript('''CREATE TABLE products(barcode TEXT PRIMARY KEY,description TEXT,cost_price REAL);
    CREATE TABLE sales_history(id INTEGER PRIMARY KEY,timestamp TEXT,voided INTEGER DEFAULT 0,status TEXT DEFAULT 'COMPLETED');
    CREATE TABLE sale_items(id INTEGER,sale_id INTEGER,barcode TEXT,description TEXT,qty REAL,price REAL);''')
    c.execute("INSERT INTO products VALUES('A','Widget',6)")
    c.execute("INSERT INTO sales_history VALUES(1,'2026-09-10 10:00',0,'COMPLETED')")
    c.execute("INSERT INTO sale_items VALUES(1,1,'A','Widget',10,10)")
    c.commit(); return c

def test_price_and_volume_scenario():
    c=db(); r=scenario_rows(c,'2026-09-01','2026-09-10',10,-10)[0]
    assert round(r[8],2)==11.0
    assert round(r[7],2)==9.0
    assert round(r[10],2)==45.0
    assert round(r[12],2)==5.0

def test_voided_sales_excluded():
    c=db(); c.execute("UPDATE sales_history SET voided=1"); c.commit()
    assert scenario_rows(c,'2026-09-01','2026-09-10',5,0)==[]
