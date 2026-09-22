import sqlite3, unittest
from services.cashier_workflow import ensure_schema, open_shift, close_shift
from services.cashup_hardening import ensure_schema as ensure_cashup_schema, validate_denominations, validate_cashup

class Phase67CashupHardeningTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:')
        self.c.executescript('''
        CREATE TABLE cashier_shifts(id INTEGER PRIMARY KEY AUTOINCREMENT,cashier TEXT NOT NULL,opened_at TEXT NOT NULL,opening_cash REAL DEFAULT 0,closed_at TEXT,closing_cash REAL,expected_cash REAL,difference REAL,status TEXT DEFAULT 'OPEN');
        CREATE TABLE sales_history(id INTEGER PRIMARY KEY,timestamp TEXT,total_amount REAL,cashier TEXT,voided INTEGER DEFAULT 0,status TEXT DEFAULT 'COMPLETED',payment_type TEXT,cash_amount REAL DEFAULT 0,card_amount REAL DEFAULT 0);
        CREATE TABLE cashup_records(id INTEGER PRIMARY KEY AUTOINCREMENT,cashup_date TEXT,cashier TEXT,opening_float REAL,expected_cash REAL,actual_cash REAL,difference REAL);
        ''')
        ensure_schema(self.c); ensure_cashup_schema(self.c)
    def tearDown(self): self.c.close()
    def test_denominations_total(self):
        counts, total = validate_denominations({'100':1,'20':2,'5':1,'0.5':1})
        self.assertEqual(total,145.5); self.assertEqual(counts['100'],1)
    def test_count_must_match_actual_and_variance_needs_reason(self):
        with self.assertRaises(ValueError): validate_cashup(expected_cash=100, actual_cash=99, denomination_counts={'100':1})
        with self.assertRaises(ValueError): validate_cashup(expected_cash=100, actual_cash=99, denomination_counts={'50':1,'20':2,'5':1,'2':2}, variance_reason='')
        r=validate_cashup(expected_cash=100, actual_cash=99, denomination_counts={'50':1,'20':2,'5':1,'2':2}, variance_reason='Short cash')
        self.assertEqual(r['difference'],-1)
    def test_database_guard_and_close_snapshot(self):
        sid=open_shift(self.c,cashier='alice',opening_cash=100)
        with self.assertRaises(sqlite3.IntegrityError): self.c.execute("INSERT INTO cashier_shifts(cashier,opened_at,status) VALUES('alice',datetime('now'),'OPEN')")
        result=close_shift(self.c,shift_id=sid,actual_cash=100,denomination_counts={'100':1})
        self.c.commit()
        self.assertEqual(result['difference'],0)
        row=self.c.execute('SELECT difference,count_json,counted_at FROM cashup_records WHERE shift_id=?',(sid,)).fetchone()
        self.assertEqual(row[0],0); self.assertIn('\"100\"',row[1]); self.assertTrue(row[2])
    def test_nonzero_variance_close_requires_reason(self):
        sid=open_shift(self.c,cashier='bob',opening_cash=100); self.c.commit()
        with self.assertRaises(ValueError): close_shift(self.c,shift_id=sid,actual_cash=95,denomination_counts={'50':1,'20':2,'5':1})
        self.c.rollback()
        # Still open after failed validation.
        self.assertEqual(self.c.execute('SELECT status FROM cashier_shifts WHERE id=?',(sid,)).fetchone()[0],'OPEN')

if __name__=='__main__': unittest.main()
