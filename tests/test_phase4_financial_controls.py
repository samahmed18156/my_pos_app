import os, sqlite3, tempfile, unittest
from services.financial_controls_service import payment_reconciliation, cashup_exceptions, customer_ageing, supplier_ageing, financial_exceptions

class Phase4FinancialControlsTests(unittest.TestCase):
    def setUp(self):
        f=tempfile.NamedTemporaryFile(delete=False); f.close(); self.path=f.name
        self.c=sqlite3.connect(self.path)
        self.c.executescript('''
        CREATE TABLE sales_history(id INTEGER PRIMARY KEY,timestamp TEXT,total_amount REAL,cash_amount REAL,card_amount REAL,payment_type TEXT,voided INTEGER DEFAULT 0,branch_id INTEGER);
        CREATE TABLE cashup_records(id INTEGER PRIMARY KEY,cashup_date TEXT,cashier TEXT,opening_float REAL,expected_cash REAL,actual_cash REAL,difference REAL);
        CREATE TABLE customers(id INTEGER PRIMARY KEY,name TEXT);
        CREATE TABLE customer_account_invoices(id INTEGER PRIMARY KEY,customer_id INTEGER,invoice_date TEXT,total REAL,paid REAL,outstanding REAL,status TEXT);
        CREATE TABLE grn_headers(id INTEGER PRIMARY KEY,supplier_id INTEGER,supplier_name TEXT,created_at TEXT,total REAL,paid REAL,outstanding REAL,status TEXT);
        INSERT INTO customers VALUES(1,'Alice'),(2,'Bob');
        INSERT INTO sales_history VALUES(1,'2026-09-10 08:00',100,70,40,'Cash',0,1);
        INSERT INTO sales_history VALUES(2,'2026-09-10 09:00',50,0,50,'Card',0,1);
        INSERT INTO cashup_records VALUES(1,'2026-09-10','alice',100,160,158,-2);
        INSERT INTO cashup_records VALUES(2,'2026-09-10','bob',100,100,100,0);
        INSERT INTO customer_account_invoices VALUES(1,1,'2026-08-01',500,100,400,'PART PAID');
        INSERT INTO customer_account_invoices VALUES(2,2,'2026-09-01',200,0,200,'UNPAID');
        INSERT INTO grn_headers VALUES(1,7,'Supplier A','2026-07-01',1000,400,600,'PART PAID');
        '''); self.c.commit()
    def tearDown(self): self.c.close(); os.unlink(self.path)
    def test_payment_reconciliation(self):
        r=payment_reconciliation(self.c,start_date='2026-09-10',end_date='2026-09-10'); self.assertEqual(r['sales'],150); self.assertEqual(r['components'],160); self.assertEqual(r['difference'],10); self.assertEqual(r['status'],'EXCEPTION')
    def test_cashup_exceptions(self):
        r=cashup_exceptions(self.c,date='2026-09-10'); self.assertEqual(len(r),2); self.assertEqual(r[0]['status'],'EXCEPTION'); self.assertEqual(r[1]['status'],'OK')
    def test_customer_ageing(self):
        r=customer_ageing(self.c,as_of='2026-09-10'); self.assertEqual(len(r),2); self.assertEqual(r[0][5],'31-60'); self.assertEqual(r[1][5],'0-30')
    def test_supplier_ageing(self):
        r=supplier_ageing(self.c,as_of='2026-09-10'); self.assertEqual(r[0][5],'61-90')
    def test_financial_exceptions(self):
        r=financial_exceptions(self.c,start_date='2026-09-10',end_date='2026-09-10'); self.assertTrue(any(x[0]=='PAYMENT' for x in r)); self.assertTrue(any(x[0]=='CASHUP' for x in r))

if __name__=='__main__': unittest.main()
