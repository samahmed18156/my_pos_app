import os, sqlite3, tempfile, unittest
from services.tax_profit_stock_audit import audit

class TaxProfitStockAuditTests(unittest.TestCase):
    def setUp(self):
        f=tempfile.NamedTemporaryFile(delete=False); f.close(); self.path=f.name
        c=self.c=sqlite3.connect(self.path)
        c.executescript('''
        CREATE TABLE products(barcode TEXT PRIMARY KEY,description TEXT,cost_price REAL,soh REAL);
        CREATE TABLE branches(id INTEGER PRIMARY KEY,name TEXT);
        CREATE TABLE branch_stock(branch_id INTEGER,barcode TEXT,soh REAL,PRIMARY KEY(branch_id,barcode));
        CREATE TABLE sales_history(id INTEGER PRIMARY KEY,timestamp TEXT,total_amount REAL,total_cost REAL,voided INTEGER DEFAULT 0,branch_id INTEGER,cash_amount REAL,card_amount REAL);
        CREATE TABLE return_history(id INTEGER PRIMARY KEY,timestamp TEXT,original_sale_id INTEGER,total_amount REAL);
        CREATE TABLE return_items(id INTEGER PRIMARY KEY,return_id INTEGER,sale_item_id INTEGER,barcode TEXT,qty REAL);
        CREATE TABLE sale_items(id INTEGER PRIMARY KEY,sale_id INTEGER,barcode TEXT,qty REAL);
        CREATE TABLE grn_headers(id INTEGER PRIMARY KEY,grn_no TEXT,supplier_id INTEGER,vat_mode TEXT,subtotal REAL,vat REAL,total REAL,created_at TEXT);
        CREATE TABLE grn_items(id INTEGER PRIMARY KEY,grn_id INTEGER,barcode TEXT,qty_received REAL,cost_price REAL,value REAL);
        CREATE TABLE supplier_credits(id INTEGER PRIMARY KEY,credit_no TEXT,supplier_id INTEGER,credit_date TEXT,amount REAL);
        CREATE TABLE supplier_credit_items(id INTEGER PRIMARY KEY,credit_id INTEGER,grn_id INTEGER,grn_item_id INTEGER,barcode TEXT,qty REAL,unit_cost REAL,value REAL);
        CREATE TABLE operating_expenses(id INTEGER PRIMARY KEY,expense_date TEXT,amount_ex_vat REAL,vat_amount REAL,total_amount REAL,branch_id INTEGER);
        INSERT INTO branches VALUES(1,'Main');
        INSERT INTO products VALUES('A','Widget',11.50,10);
        INSERT INTO branch_stock VALUES(1,'A',10);
        INSERT INTO sales_history VALUES(1,'2026-09-08 10:00',115,57.50,0,1,115,0);
        INSERT INTO sale_items VALUES(1,1,'A',5);
        INSERT INTO grn_headers VALUES(1,'GRN-1',7,'Inclusive',86.96,13.04,100,'2026-09-08');
        INSERT INTO grn_items VALUES(1,1,'A',10,10,100);
        INSERT INTO operating_expenses VALUES(1,'2026-09-08',10,1.50,11.50,1);
        ''')
        c.commit()
    def tearDown(self): self.c.close(); os.unlink(self.path)
    def test_vat_profit_and_stock_reconcile(self):
        a=audit(self.c,start_date='2026-09-08',end_date='2026-09-08')
        self.assertEqual(a['sales']['gross_inclusive'],115.0)
        self.assertEqual(a['sales']['output_vat'],15.0)
        self.assertEqual(a['sales']['net_sales_ex_vat'],100.0)
        self.assertEqual(a['purchases']['input_vat'],13.04)
        self.assertEqual(a['expenses']['expense_vat'],1.50)
        self.assertEqual(a['cogs_ex_vat'],50.0)
        self.assertEqual(a['gross_profit_ex_vat'],50.0)
        self.assertEqual(a['net_profit_ex_vat'],40.0)
        self.assertEqual(a['vat_payable_before_adjustments'],0.46)
        self.assertTrue(a['stock_balanced'])
    def test_supplier_credit_reduces_input_vat(self):
        self.c.execute("INSERT INTO supplier_credits VALUES(1,'SCN-1',7,'2026-09-08',23.00)")
        self.c.execute("INSERT INTO supplier_credit_items VALUES(1,1,1,1,'A',2,11.50,23.00)")
        self.c.commit()
        a=audit(self.c,start_date='2026-09-08',end_date='2026-09-08')
        self.assertEqual(a['purchases']['supplier_credit_vat'],3.0)
        self.assertEqual(a['vat_payable_before_adjustments'],3.46)
    def test_stock_mismatch_is_reported(self):
        self.c.execute("UPDATE branch_stock SET soh=9 WHERE barcode='A'")
        self.c.commit()
        a=audit(self.c)
        self.assertFalse(a['stock_balanced'])
        self.assertEqual(a['stock']['units_difference'],1.0)

if __name__=='__main__': unittest.main()
