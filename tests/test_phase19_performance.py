import sqlite3, os
from performance_scalability import index_inventory, optimize_indexes, database_metrics, query_plan, export_indexes

def make_db(tmp):
    p=os.path.join(tmp,'pos.db'); c=sqlite3.connect(p)
    c.executescript('''CREATE TABLE sales_history(id INTEGER PRIMARY KEY,timestamp TEXT,status TEXT,voided INTEGER,branch_id INTEGER); CREATE TABLE sale_items(id INTEGER PRIMARY KEY,sale_id INTEGER,barcode TEXT); CREATE TABLE products(id INTEGER PRIMARY KEY,barcode TEXT,active INTEGER,soh REAL); CREATE TABLE cashier_shifts(id INTEGER PRIMARY KEY,opened_at TEXT,status TEXT); CREATE TABLE audit_log(id INTEGER PRIMARY KEY,timestamp TEXT,user_id INTEGER); INSERT INTO sales_history VALUES(1,'2026-09-10','COMPLETED',0,1);'''); c.commit(); c.close(); return p

def test_metrics(tmp_path):
    p=make_db(tmp_path); m=database_metrics(p); assert m['exists'] and m['tables']==5 and m['rows']==1 and m['integrity']=='ok'

def test_index_optimizer_is_additive(tmp_path):
    p=make_db(tmp_path); before=database_metrics(p)['rows']; r=optimize_indexes(p); after=database_metrics(p)['rows']; assert r['created']>0 and before==after
    assert sum(x['present'] and x['applicable'] for x in index_inventory(p))>0

def test_optimizer_idempotent(tmp_path):
    p=make_db(tmp_path); first=optimize_indexes(p); second=optimize_indexes(p); assert first['created']>0 and second['created']==0

def test_query_plan_and_export(tmp_path):
    p=make_db(tmp_path); plan=query_plan(p); assert plan and not str(plan[0][-1]).startswith('ERROR')
    out=tmp_path/'indexes.csv'; export_indexes(index_inventory(p),out); assert out.exists() and 'idx_sales_history_timestamp_status' in out.read_text()
