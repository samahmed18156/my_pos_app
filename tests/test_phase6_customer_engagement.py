import sqlite3
import customer_engagement as ce


def test_promotion_schema_and_upsert(tmp_path, monkeypatch):
    db=tmp_path/'phase6.db'; monkeypatch.setattr(ce,'DB_NAME',str(db))
    ce.ensure_schema()
    ce.save_promotion('Weekend Sale','Percentage',10,'2026-09-01','2026-09-30',100)
    ce.save_promotion('Weekend Sale','Percentage',15,'2026-09-02','2026-09-30',200,'1','updated')
    rows=ce.promotion_rows()
    assert len(rows)==1
    assert rows[0][3]==15
    assert rows[0][6]==200


def test_promotion_rejects_bad_dates(tmp_path, monkeypatch):
    monkeypatch.setattr(ce,'DB_NAME',str(tmp_path/'p.db'))
    ce.ensure_schema()
    try:
        ce.save_promotion('Bad','Percentage',10,'2026-10-01','2026-09-01')
        assert False
    except ValueError as exc:
        assert 'end date' in str(exc)


def test_customer_segments_exclude_voided_and_incomplete(tmp_path, monkeypatch):
    db=tmp_path/'c.db'; monkeypatch.setattr(ce,'DB_NAME',str(db))
    c=sqlite3.connect(db)
    c.executescript('''CREATE TABLE customers(id INTEGER PRIMARY KEY,name TEXT,phone TEXT,active INTEGER DEFAULT 1);
    CREATE TABLE sales_history(id INTEGER PRIMARY KEY,timestamp TEXT,total_amount REAL,customer_id INTEGER,voided INTEGER DEFAULT 0,status TEXT DEFAULT 'COMPLETED');''')
    c.execute("INSERT INTO customers VALUES(1,'Alice','123',1)")
    c.execute("INSERT INTO sales_history VALUES(1,'2026-09-10',5000,1,0,'COMPLETED')")
    c.execute("INSERT INTO sales_history VALUES(2,'2026-09-10',9000,1,1,'COMPLETED')")
    c.execute("INSERT INTO sales_history VALUES(3,'2026-09-10',9000,1,0,'PENDING')")
    c.commit(); c.close()
    rows=ce.customer_segments(start_date='2026-09-01',end_date='2026-09-30')
    assert rows[0]['spend']==5000
    assert rows[0]['segment']=='Loyal'
    assert rows[0]['points']==500
