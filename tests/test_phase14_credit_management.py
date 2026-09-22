import sqlite3
from credit_management import customer_credit, customer_ageing_detail, supplier_credit, supplier_ageing_detail, credit_summary

def db():
 c=sqlite3.connect(':memory:'); c.executescript('''
 CREATE TABLE customers(id INTEGER PRIMARY KEY,name TEXT,phone TEXT,credit_limit REAL,active INTEGER);
 CREATE TABLE customer_account_transactions(id INTEGER PRIMARY KEY,customer_id INTEGER,txn_date TEXT,debit REAL,credit REAL);
 CREATE TABLE customer_account_invoices(id INTEGER PRIMARY KEY,customer_id INTEGER,sale_id INTEGER,invoice_no TEXT,invoice_date TEXT,total REAL,paid REAL,outstanding REAL,status TEXT);
 CREATE TABLE accounts(id INTEGER PRIMARY KEY,name TEXT,type TEXT,supplier_account_no TEXT,credit_limit REAL,payment_terms TEXT,active INTEGER);
 CREATE TABLE account_transactions(id INTEGER PRIMARY KEY,account_id INTEGER,txn_type TEXT,total_amount REAL,txn_date TEXT);
 CREATE TABLE supplier_payments(id INTEGER PRIMARY KEY,supplier_id INTEGER,payment_date TEXT,amount REAL);
 CREATE TABLE supplier_credits(id INTEGER PRIMARY KEY,supplier_id INTEGER,credit_date TEXT,amount REAL);
 CREATE TABLE grn_headers(id INTEGER PRIMARY KEY,supplier_id INTEGER,supplier_name TEXT,created_at TEXT,outstanding REAL);
 INSERT INTO customers VALUES(1,'Alice','123',1000,1),(2,'Bob','456',500,1);
 INSERT INTO customer_account_transactions VALUES(1,1,'2026-09-01',950,0),(2,1,'2026-09-05',0,100),(3,2,'2026-09-02',600,0);
 INSERT INTO customer_account_invoices VALUES(1,1,10,'INV-10','2026-08-01',850,0,850,'UNPAID');
 INSERT INTO accounts VALUES(7,'Supplier One','Supplier','SUP-000007',2000,'30 Days',1);
 INSERT INTO account_transactions VALUES(1,7,'PURCHASE',1500,'2026-08-01');
 INSERT INTO supplier_payments VALUES(1,7,'2026-08-15',200);
 INSERT INTO supplier_credits VALUES(1,7,'2026-08-20',100);
 INSERT INTO grn_headers VALUES(1,7,'Supplier One','2026-07-01',1200);
 '''); return c

def test_customer_credit_and_risk():
 c=db(); r=customer_credit(c,'2026-09-10'); assert r[0][3]==850 and r[0][6]==85.0 and r[0][9]=='HIGH'; assert r[1][9]=='OVER LIMIT'

def test_customer_ageing():
 c=db(); r=customer_ageing_detail(c,'2026-09-10'); assert r[0][8]=='31-60'

def test_supplier_credit():
 c=db(); r=supplier_credit(c,'2026-09-10')[0]; assert r[6]==1200 and r[8]==60.0

def test_supplier_ageing_and_summary():
 c=db(); assert supplier_ageing_detail(c,'2026-09-10')[0][5]=='61-90'; s=credit_summary(c,'2026-09-10'); assert s['customer_balance']==1450 and s['supplier_balance']==1200
