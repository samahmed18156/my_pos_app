import sqlite3, unittest

class Phase32DocumentHistoryTests(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:')
        self.c.executescript('''
        CREATE TABLE sales_history(id INTEGER PRIMARY KEY,timestamp TEXT,total_amount REAL,customer_name TEXT,voided INTEGER DEFAULT 0);
        CREATE TABLE grn_headers(id INTEGER PRIMARY KEY,created_at TEXT,grn_no TEXT,total REAL,supplier_name TEXT);
        CREATE TABLE return_history(id INTEGER PRIMARY KEY,timestamp TEXT,original_sale_id INTEGER,total_amount REAL,refund_type TEXT,cashier TEXT,reason TEXT);
        CREATE TABLE credit_notes(id INTEGER PRIMARY KEY,timestamp TEXT,invoice_ref TEXT,total_amount REAL);
        CREATE TABLE supplier_credits(id INTEGER PRIMARY KEY,credit_no TEXT,credit_date TEXT,amount REAL,reason TEXT);
        CREATE TABLE customer_account_payments(id INTEGER PRIMARY KEY,amount REAL,payment_method TEXT,reference TEXT,created_at TEXT);
        CREATE TABLE supplier_payments(id INTEGER PRIMARY KEY,payment_no TEXT,payment_date TEXT,amount REAL,supplier_name TEXT);
        ''')
        self.c.executescript('''
        INSERT INTO sales_history VALUES(1,'2026-09-08 09:00',115,'Acme',0);
        INSERT INTO grn_headers VALUES(2,'2026-09-08 10:00','GRN-001',500,'Supplier One');
        INSERT INTO return_history VALUES(3,'2026-09-08 11:00',1,20,'Credit Note','cashier','return');
        INSERT INTO credit_notes VALUES(4,'2026-09-08 12:00','INV-1',30);
        INSERT INTO supplier_credits VALUES(5,'SCN-001','2026-09-08',40,'Damaged');
        INSERT INTO customer_account_payments VALUES(6,50,'Cash','RCTREF','2026-09-08 13:00');
        INSERT INTO supplier_payments VALUES(7,'PAY-001','2026-09-08',60,'Supplier One');
        ''')
    def tearDown(self): self.c.close()
    def test_all_supported_documents_are_discoverable(self):
        expected=7
        total=0
        for table in ('sales_history','grn_headers','return_history','credit_notes','supplier_credits','customer_account_payments','supplier_payments'):
            total += self.c.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
        self.assertEqual(total, expected)
    def test_selected_sale_is_exact_document(self):
        row=self.c.execute('SELECT id,total_amount,customer_name FROM sales_history WHERE id=?',(1,)).fetchone()
        self.assertEqual(row,(1,115.0,'Acme'))
    def test_selected_supplier_credit_is_exact_document(self):
        row=self.c.execute('SELECT credit_no,amount FROM supplier_credits WHERE id=?',(5,)).fetchone()
        self.assertEqual(row,('SCN-001',40.0))
    def test_history_is_read_only_by_design(self):
        before=self.c.execute('SELECT COUNT(*) FROM sales_history').fetchone()[0]
        self.c.execute('SELECT * FROM sales_history WHERE id=?',(1,)).fetchone()
        after=self.c.execute('SELECT COUNT(*) FROM sales_history').fetchone()[0]
        self.assertEqual(before,after)

if __name__=='__main__': unittest.main()
