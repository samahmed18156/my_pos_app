import sqlite3
from end_of_day_operations import close_readiness, period_summary

def db():
 c=sqlite3.connect(':memory:'); c.executescript('''CREATE TABLE sales_history(id INTEGER PRIMARY KEY,timestamp TEXT,total_amount REAL,total_cost REAL,cash_amount REAL,card_amount REAL,voided INTEGER DEFAULT 0,status TEXT,branch_id INTEGER); INSERT INTO sales_history VALUES(1,'2026-09-10 09:00',115,70,115,0,0,'COMPLETED',1); CREATE TABLE return_history(id INTEGER PRIMARY KEY,timestamp TEXT,original_sale_id INTEGER,total_amount REAL,refund_type TEXT,cashier TEXT); CREATE TABLE return_items(id INTEGER PRIMARY KEY,return_id INTEGER,sale_item_id INTEGER,barcode TEXT,qty REAL); CREATE TABLE products(id INTEGER PRIMARY KEY,barcode TEXT,soh REAL,cost_price REAL,active INTEGER DEFAULT 1); INSERT INTO products VALUES(1,'X',5,70,1); CREATE TABLE cashier_shifts(id INTEGER PRIMARY KEY,cashier TEXT,opened_at TEXT,closed_at TEXT,status TEXT,difference REAL); INSERT INTO cashier_shifts VALUES(1,'Alice','2026-09-10 08:00','2026-09-10 17:00','CLOSED',0); CREATE TABLE cashup_records(cashup_date TEXT,cashier TEXT,difference REAL); INSERT INTO cashup_records VALUES('2026-09-10','Alice',0); CREATE TABLE staged_conflicts(id INTEGER PRIMARY KEY); CREATE TABLE operating_expenses(id INTEGER PRIMARY KEY,expense_date TEXT,total_amount REAL,vat_amount REAL,branch_id INTEGER,payment_method TEXT);'''); return c

def test_period_summary():
 c=db(); s=period_summary(c,'2026-09-10','2026-09-10'); assert s['net_sales']==115; assert s['transactions']==1; assert s['open_shifts']==0

def test_close_readiness_all_clear():
 c=db(); assert all(x[1]=='PASS' for x in close_readiness(c,'2026-09-10'))

def test_open_shift_is_review():
 c=db(); c.execute("UPDATE cashier_shifts SET status='OPEN',closed_at=NULL WHERE id=1"); assert any(x[0]=='Cashier shifts' and x[1]=='REVIEW' for x in close_readiness(c,'2026-09-10'))

def test_cash_variance_is_review():
 c=db(); c.execute("UPDATE cashup_records SET difference=10"); assert any(x[0]=='Cash-up variance' and x[1]=='REVIEW' for x in close_readiness(c,'2026-09-10'))
