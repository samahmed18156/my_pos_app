import sqlite3
from compliance_control import audit_activity, compliance_exceptions, compliance_summary

def db():
    c=sqlite3.connect(':memory:')
    c.executescript('''
    CREATE TABLE audit_log(id INTEGER PRIMARY KEY,event_time TEXT,username TEXT,event_type TEXT,description TEXT,reference_type TEXT,reference_id TEXT,details_json TEXT);
    CREATE TABLE cashier_shifts(id INTEGER PRIMARY KEY,cashier TEXT,opened_at TEXT,closed_at TEXT,status TEXT,difference REAL);
    CREATE TABLE sales_history(id INTEGER PRIMARY KEY,timestamp TEXT,voided INTEGER,total_amount REAL);
    CREATE TABLE return_history(id INTEGER PRIMARY KEY,timestamp TEXT,total_amount REAL);
    CREATE TABLE products(id INTEGER PRIMARY KEY,soh REAL);
    CREATE TABLE staged_conflicts(id INTEGER PRIMARY KEY);
    INSERT INTO audit_log VALUES(1,'2026-09-10 08:00','admin','LOGIN_FAILED','',NULL,NULL,'{}');
    INSERT INTO cashier_shifts VALUES(1,'Alice','2026-09-10 07:00','2026-09-10 15:00','CLOSED',5);
    INSERT INTO sales_history VALUES(1,'2026-09-10 09:00',1,100);
    INSERT INTO return_history VALUES(1,'2026-09-10 10:00',20);
    INSERT INTO products VALUES(1,-2);
    INSERT INTO staged_conflicts VALUES(1);
    ''')
    return c

def test_activity():
    c=db(); a=audit_activity(c,'2026-09-10','2026-09-10'); assert a['events']==1 and a['failed_logins']==1

def test_exceptions():
    c=db(); e=compliance_exceptions(c,'2026-09-10','2026-09-10'); cats={x[0] for x in e}; assert {'Cash','Sales','Returns','Stock','Sync','Security'} <= cats

def test_summary_score():
    c=db(); s=compliance_summary(c,'2026-09-10','2026-09-10'); assert s['total']>=6 and 0 <= s['score'] <= 100
