import os, sqlite3, tempfile, unittest
import shift_control

class Phase11Tests(unittest.TestCase):
    def setUp(self):
        self.f=tempfile.NamedTemporaryFile(delete=False,suffix='.db'); self.f.close()
        self.c=sqlite3.connect(self.f.name)
        self.c.executescript('''
        CREATE TABLE cashier_shifts(id INTEGER PRIMARY KEY, cashier TEXT, opened_at TEXT, opening_cash REAL, closed_at TEXT, closing_cash REAL, expected_cash REAL, difference REAL, status TEXT);
        CREATE TABLE sales_history(id INTEGER PRIMARY KEY,timestamp TEXT,total_amount REAL,cashier TEXT,voided INTEGER DEFAULT 0,status TEXT DEFAULT 'COMPLETED');
        CREATE TABLE return_history(id INTEGER PRIMARY KEY,timestamp TEXT,total_amount REAL,cashier TEXT);
        INSERT INTO cashier_shifts VALUES(1,'Alice','2026-09-10 08:00',500,'2026-09-10 17:00',1500,1490,10,'CLOSED');
        INSERT INTO cashier_shifts VALUES(2,'Bob','2026-09-10 08:00',300,NULL,NULL,0,0,'OPEN');
        INSERT INTO sales_history VALUES(1,'2026-09-10 09:00',100,'Alice',0,'COMPLETED');
        INSERT INTO sales_history VALUES(2,'2026-09-10 10:00',200,'Alice',0,'COMPLETED');
        INSERT INTO sales_history VALUES(3,'2026-09-10 11:00',999,'Alice',1,'VOID');
        INSERT INTO return_history VALUES(1,'2026-09-10 12:00',20,'Alice');
        ''')
        self.c.commit(); shift_control.DB_PATH=self.f.name
    def tearDown(self): self.c.close(); os.unlink(self.f.name)
    def test_shift_summary_and_exceptions(self):
        rows=shift_control.shift_summary(self.c,'2026-09-10','2026-09-10'); alice=next(r for r in rows if r[1]=='Alice'); self.assertEqual(alice[9],300)
        ex=shift_control.shift_exceptions(self.c,'2026-09-10','2026-09-10'); self.assertEqual(len(ex),2)
    def test_cashier_performance_excludes_voids(self):
        rows=shift_control.cashier_performance(self.c,'2026-09-10','2026-09-10'); self.assertEqual(rows[0][1],300); self.assertEqual(rows[0][2],2); self.assertEqual(rows[0][4],1); self.assertEqual(rows[0][5],20)

if __name__=='__main__': unittest.main()
