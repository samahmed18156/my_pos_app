import sqlite3, unittest
from services.cashier_workflow import ensure_schema, open_shift, get_open_shift, record_cash_movement, shift_cash_summary, close_shift

class Phase66CashierWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:')
        self.c.executescript('''
        CREATE TABLE cashier_shifts(id INTEGER PRIMARY KEY AUTOINCREMENT,cashier TEXT NOT NULL,opened_at DATETIME NOT NULL,opening_cash REAL DEFAULT 0,closed_at DATETIME,closing_cash REAL,expected_cash REAL,difference REAL,status TEXT DEFAULT 'OPEN');
        CREATE TABLE sales_history(id INTEGER PRIMARY KEY,timestamp TEXT,total_amount REAL,cashier TEXT,voided INTEGER DEFAULT 0,status TEXT DEFAULT 'COMPLETED',payment_type TEXT,cash_amount REAL DEFAULT 0,card_amount REAL DEFAULT 0);
        CREATE TABLE return_history(id INTEGER PRIMARY KEY,timestamp TEXT,total_amount REAL,refund_type TEXT,cashier TEXT,original_sale_id INTEGER);
        CREATE TABLE customer_account_payments(id INTEGER PRIMARY KEY,customer_id INTEGER,payment_date TEXT,amount REAL,payment_method TEXT,cashier TEXT);
        CREATE TABLE supplier_payments(id INTEGER PRIMARY KEY,amount REAL,payment_date TEXT,payment_method TEXT,cashier TEXT);
        CREATE TABLE operating_expenses(id INTEGER PRIMARY KEY,total_amount REAL,expense_date TEXT,payment_method TEXT,captured_by TEXT);
        CREATE TABLE cashup_records(id INTEGER PRIMARY KEY,cashup_date TEXT,cashier TEXT,opening_float REAL,expected_cash REAL,actual_cash REAL,difference REAL);
        INSERT INTO sales_history VALUES(1,'2026-09-11 09:00',100,'alice',0,'COMPLETED','Cash',100,0);
        INSERT INTO sales_history VALUES(2,'2026-09-11 10:00',50,'alice',0,'COMPLETED','Card',0,50);
        INSERT INTO return_history VALUES(1,'2026-09-11 11:00',20,'Cash Refund','alice',1);
        INSERT INTO customer_account_payments VALUES(1,1,'2026-09-11 12:00',30,'Cash','alice');
        INSERT INTO supplier_payments VALUES(1,15,'2026-09-11 13:00','Cash','alice');
        INSERT INTO operating_expenses VALUES(1,5,'2026-09-11 09:00','Cash','alice');
        '''); self.c.commit()
    def tearDown(self): self.c.close()
    def test_open_duplicate_and_summary(self):
        sid=open_shift(self.c,cashier='alice',opening_cash=100); self.c.execute("UPDATE cashier_shifts SET opened_at='2026-09-11 08:00:00' WHERE id=?",(sid,)); self.c.commit()
        self.assertEqual(get_open_shift(self.c,'alice')[0],sid)
        with self.assertRaises(ValueError): open_shift(self.c,cashier='alice',opening_cash=100)
        record_cash_movement(self.c,shift_id=sid,cashier='alice',movement_type='PAY_IN',amount=10,reason='Float top-up')
        record_cash_movement(self.c,shift_id=sid,cashier='alice',movement_type='PAY_OUT',amount=5,reason='Petty cash')
        s=shift_cash_summary(self.c,sid)
        self.assertEqual(s['cash_sales'],100); self.assertEqual(s['customer_cash_payments'],30)
        self.assertEqual(s['cash_refunds'],20); self.assertEqual(s['supplier_cash_payouts'],15); self.assertEqual(s['cash_expenses'],5)
        self.assertEqual(s['expected_cash'],195)
    def test_close_shift_records_variance_and_cashup(self):
        sid=open_shift(self.c,cashier='alice',opening_cash=100); self.c.execute("UPDATE cashier_shifts SET opened_at='2026-09-11 08:00:00' WHERE id=?",(sid,)); self.c.commit()
        result=close_shift(self.c,shift_id=sid,actual_cash=185,variance_reason='Till short'); self.c.commit()
        self.assertEqual(result['expected_cash'],190); self.assertEqual(result['difference'],-5)
        row=self.c.execute('SELECT status,closing_cash,expected_cash,difference FROM cashier_shifts WHERE id=?',(sid,)).fetchone()
        self.assertEqual(row,('CLOSED',185,190,-5))
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM cashup_records').fetchone()[0],1)
        with self.assertRaises(ValueError): close_shift(self.c,shift_id=sid,actual_cash=195)
    def test_payout_requires_reason(self):
        sid=open_shift(self.c,cashier='bob',opening_cash=0)
        with self.assertRaises(ValueError): record_cash_movement(self.c,shift_id=sid,cashier='bob',movement_type='PAY_OUT',amount=10)

if __name__=='__main__': unittest.main()
