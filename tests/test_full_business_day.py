import os, sqlite3, tempfile, unittest
from services import branch_stock_service, sales_service, returns_service, grn_service, supplier_credit_service, accounts_service
from services.financial_reconciliation import financial_summary, customer_balance, supplier_balance
from services.financial_service import cashup_summary
from services.business_day_service import business_day_summary


class FullBusinessDayTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp(suffix='.db'); os.close(fd)
        self.c = sqlite3.connect(self.path)
        self.c.executescript('''
        CREATE TABLE branches(id INTEGER PRIMARY KEY,name TEXT); INSERT INTO branches VALUES(1,'Main'),(2,'Branch 2');
        CREATE TABLE products(barcode TEXT PRIMARY KEY,description TEXT,cost_price REAL,selling_price REAL,soh REAL,active INTEGER DEFAULT 1);
        INSERT INTO products VALUES('A','Widget',10,23,20,1),('B','Cable',5,12,10,1);
        CREATE TABLE branch_stock(branch_id INTEGER,barcode TEXT,soh REAL,PRIMARY KEY(branch_id,barcode));
        CREATE TABLE stock_movements(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp TEXT,barcode TEXT,description TEXT,movement_type TEXT,qty REAL,qty_before REAL,qty_after REAL,cost_price REAL,reference TEXT,reason TEXT,cashier TEXT);
        CREATE TABLE sales_history(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp TEXT,total_amount REAL,total_cost REAL,payment_type TEXT,cashier TEXT,customer_id INTEGER,customer_account TEXT,customer_name TEXT,branch_id INTEGER,branch_name TEXT,cash_amount REAL DEFAULT 0,card_amount REAL DEFAULT 0,amount_tendered REAL DEFAULT 0,change_amount REAL DEFAULT 0,voided INTEGER DEFAULT 0,voided_at TEXT,voided_by TEXT);
        CREATE TABLE sale_items(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER,barcode TEXT,description TEXT,qty REAL,price REAL,value REAL);
        CREATE TABLE return_history(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp TEXT DEFAULT CURRENT_TIMESTAMP,original_sale_id INTEGER,total_amount REAL,refund_type TEXT,cashier TEXT,reason TEXT);
        CREATE TABLE return_items(id INTEGER PRIMARY KEY AUTOINCREMENT,return_id INTEGER,sale_item_id INTEGER,barcode TEXT,description TEXT,qty REAL,price REAL,value REAL);
        CREATE TABLE customers(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT,phone TEXT,address TEXT,email TEXT,credit_limit REAL DEFAULT 0,active INTEGER DEFAULT 1,created_at TEXT);
        CREATE TABLE customer_account_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,customer_id INTEGER,txn_date TEXT DEFAULT CURRENT_TIMESTAMP,txn_type TEXT,reference TEXT,description TEXT,debit REAL DEFAULT 0,credit REAL DEFAULT 0,balance_after REAL DEFAULT 0,cashier TEXT);
        CREATE TABLE customer_account_invoices(id INTEGER PRIMARY KEY AUTOINCREMENT,customer_id INTEGER,sale_id INTEGER UNIQUE,invoice_no TEXT,invoice_date TEXT,total REAL,paid REAL,outstanding REAL,status TEXT);
        CREATE TABLE customer_account_payments(id INTEGER PRIMARY KEY AUTOINCREMENT,customer_id INTEGER,payment_date TEXT DEFAULT CURRENT_TIMESTAMP,amount REAL,payment_method TEXT,reference TEXT,notes TEXT,cashier TEXT);
        CREATE TABLE customer_account_payment_allocations(id INTEGER PRIMARY KEY AUTOINCREMENT,payment_id INTEGER,invoice_id INTEGER,amount REAL);
        CREATE TABLE accounts(id INTEGER PRIMARY KEY,name TEXT,type TEXT,supplier_account_no TEXT,credit_limit REAL DEFAULT 0);
        CREATE TABLE account_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,account_id INTEGER,txn_type TEXT,total_amount REAL,txn_date TEXT);
        CREATE TABLE supplier_payments(id INTEGER PRIMARY KEY AUTOINCREMENT,payment_no TEXT,supplier_id INTEGER,supplier_account_no TEXT,supplier_name TEXT,payment_date TEXT,amount REAL,payment_method TEXT,reference TEXT,notes TEXT,cashier TEXT,created_by TEXT);
        CREATE TABLE supplier_credits(id INTEGER PRIMARY KEY AUTOINCREMENT,credit_no TEXT UNIQUE,supplier_id INTEGER,credit_date TEXT,amount REAL,reason TEXT,reference TEXT,created_by TEXT,stock_returned REAL DEFAULT 0,item_count INTEGER DEFAULT 0);
        CREATE TABLE supplier_credit_items(id INTEGER PRIMARY KEY AUTOINCREMENT,credit_id INTEGER,grn_id INTEGER,grn_item_id INTEGER,barcode TEXT,description TEXT,qty REAL,unit_cost REAL,value REAL,created_at TEXT);
        CREATE TABLE operating_expenses(id INTEGER PRIMARY KEY AUTOINCREMENT,expense_date TEXT,reference TEXT,payee TEXT,category TEXT,description TEXT,amount_ex_vat REAL,vat_amount REAL,total_amount REAL,payment_method TEXT,branch_id INTEGER,department TEXT,invoice_reference TEXT,notes TEXT,captured_by TEXT,created_at TEXT);
        CREATE TABLE grn_headers(id INTEGER PRIMARY KEY AUTOINCREMENT,grn_no TEXT,supplier_id INTEGER,supplier_account TEXT,supplier_name TEXT,supplier_invoice TEXT,reference TEXT,vat_mode TEXT,subtotal REAL,vat REAL,total REAL,created_at TEXT,cashier TEXT);
        CREATE TABLE grn_items(id INTEGER PRIMARY KEY AUTOINCREMENT,grn_id INTEGER,barcode TEXT,description TEXT,soh_before REAL,order_qty REAL,qty_received REAL,cost_price REAL,value REAL);
        CREATE TABLE void_history(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER,amount REAL,cash_amount REAL,card_amount REAL,cashier TEXT,reason TEXT);
        CREATE TABLE transaction_controls(id INTEGER PRIMARY KEY AUTOINCREMENT,control_type TEXT,reference TEXT,amount REAL,status TEXT,notes TEXT,cashier TEXT);
        CREATE TABLE cashup_records(id INTEGER PRIMARY KEY AUTOINCREMENT,cashup_date TEXT,cashier TEXT,opening_float REAL,expected_cash REAL,actual_cash REAL,difference REAL);
        ''')
        self.c.execute("INSERT INTO customers(name,credit_limit,active,created_at) VALUES('Alice',500,1,'2026-09-07')")
        self.cid=self.c.execute('SELECT id FROM customers').fetchone()[0]
        self.c.execute("INSERT INTO accounts(id,name,type,supplier_account_no) VALUES(9,'Acme','Supplier','SUP-9')")
        self.c.commit()
        self.old=branch_stock_service.DB_NAME; branch_stock_service.DB_NAME=self.path; branch_stock_service.ensure_schema(self.c); self.c.commit()
        branch_stock_service.change_stock(self.c,1,'A',20); branch_stock_service.change_stock(self.c,1,'B',10); branch_stock_service.change_stock(self.c,2,'B',2); self.c.commit()

    def tearDown(self):
        branch_stock_service.DB_NAME=self.old; self.c.close(); os.unlink(self.path)

    def test_complete_business_day_reconciles(self):
        # 08:00 opening stock: A=40 globally after seeding branch, B=20.
        # Purchase: +5 A into branch 2 for R100 inclusive.
        grn=grn_service.post_grn(self.c,supplier_id=9,supplier_account='SUP-9',supplier_name='Acme',
            items=[{'barcode':'A','qty':5,'cost':20}],branch_id=2,cashier='manager',grn_no='GRN-DAY-1',received_date='2026-09-07 09:00:00')
        self.c.commit()
        # Cash sale at Main: 2 A for R46.
        sid1=sales_service.post_sale(self.c,cart=[{'code':'A','name':'Widget','qty':2,'price':23,'value':46}],
            total=46,total_cost=20,payment_info={'cash':46,'amount_tendered':50,'change':4},payment_type='Cash',
            cashier='alice',branch_id=1,branch_name='Main',sale_datetime='2026-09-07 10:00:00')
        self.c.commit()
        # Card sale at Branch 2: 1 A for R23.
        sales_service.post_sale(self.c,cart=[{'code':'A','name':'Widget','qty':1,'price':23,'value':23}],
            total=23,total_cost=10,payment_info={'card':23},payment_type='Card',cashier='bob',branch_id=2,branch_name='Branch 2',sale_datetime='2026-09-07 11:00:00')
        self.c.commit()
        # Credit sale at Main: 2 B for R24.
        sid3=sales_service.post_sale(self.c,cart=[{'code':'B','name':'Cable','qty':2,'price':12,'value':24}],
            total=24,total_cost=10,payment_info={},payment_type='Credit Account',cashier='alice',branch_id=1,branch_name='Main',
            customer_id=self.cid,customer_account='C-001',customer_name='Alice',sale_datetime='2026-09-07 12:00:00')
        self.c.commit()
        # Customer pays R10.
        accounts_service.customer_payment(self.c,customer_id=self.cid,amount=10,payment_method='Cash',reference='CP-DAY',cashier='alice'); self.c.commit()
        # Return one item from the cash sale: R23 cash refund.
        item=self.c.execute('SELECT id FROM sale_items WHERE sale_id=?',(sid1,)).fetchone()[0]
        returns_service.post_return(self.c,sale_id=sid1,lines=[{'sale_item_id':item,'qty':1}],refund_type='Cash Refund',cashier='alice',reason='Customer return',return_datetime='2026-09-07 13:00:00'); self.c.commit()
        # Supplier returns 1 of the GRN item for R20, reducing stock/liability.
        gi=self.c.execute('SELECT id FROM grn_items WHERE grn_id=?',(grn['grn_id'],)).fetchone()[0]
        supplier_credit_service.post_supplier_stock_credit(self.c,supplier_id=9,items=[{'grn_item_id':gi,'qty':1}],branch_id=2,credit_no='SCN-DAY',created_by='manager'); self.c.commit()
        # Pay supplier R30 by cash.
        accounts_service.supplier_payment(self.c,supplier_id=9,amount=30,payment_method='Cash',reference='SP-DAY',cashier='manager',payment_date='2026-09-07'); self.c.commit()
        # R11.50 cash operating expense at Main.
        self.c.execute("INSERT INTO operating_expenses(expense_date,reference,payee,category,description,amount_ex_vat,vat_amount,total_amount,payment_method,branch_id,captured_by) VALUES('2026-09-07','EXP-DAY','Courier','Delivery','Local delivery',10,1.5,11.5,'Cash',1,'alice')")
        self.c.commit()

        summary=business_day_summary(self.c,date='2026-09-07',opening_float=100)
        self.assertEqual(summary['financial']['gross_sales'],93.0)
        self.assertEqual(summary['financial']['returns'],23.0)
        self.assertEqual(summary['financial']['net_sales'],70.0)
        self.assertAlmostEqual(summary['financial']['cost_of_goods'],32.22,places=2)
        self.assertAlmostEqual(summary['financial']['gross_profit'],37.78,places=2)
        self.assertEqual(summary['financial']['expenses'],11.5)
        self.assertAlmostEqual(summary['financial']['net_profit'],26.28,places=2)
        self.assertEqual(customer_balance(self.c,self.cid),14.0)
        self.assertEqual(supplier_balance(self.c,9),50.0)
        cash=cashup_summary(self.c,date='2026-09-07',opening_float=100)
        # 46 cash sale + 100 float - 23 refund - 30 supplier cash - 11.50 expense = 81.50.
        self.assertEqual(round(cash['expected_cash'],2),81.50)
        self.assertEqual(cash['cash_sales'],46.0)
        self.assertEqual(cash['card_sales'],23.0)
        self.assertEqual(cash['cash_refunds'],23.0)
        self.assertEqual(cash['cash_payouts'],41.5)
        self.assertEqual(summary['negative_stock_products'],0)
        # Global stock must reconcile after purchase, sales, customer return and supplier return.
        self.assertEqual(summary['global_stock_units'], 62.0)

    def test_branch_day_reconciliation_isolated(self):
        sales_service.post_sale(self.c,cart=[{'code':'A','name':'Widget','qty':2,'price':23,'value':46}],total=46,total_cost=20,
            payment_info={'cash':46},payment_type='Cash',cashier='alice',branch_id=1,branch_name='Main',sale_datetime='2026-09-07 10:00:00'); self.c.commit()
        sales_service.post_sale(self.c,cart=[{'code':'B','name':'Cable','qty':1,'price':12,'value':5}],total=12,total_cost=5,
            payment_info={'card':12},payment_type='Card',cashier='bob',branch_id=2,branch_name='Branch 2',sale_datetime='2026-09-07 11:00:00'); self.c.commit()
        b1=financial_summary(self.c,start_date='2026-09-07',end_date='2026-09-07',branch_id=1)
        b2=financial_summary(self.c,start_date='2026-09-07',end_date='2026-09-07',branch_id=2)
        self.assertEqual(b1['gross_sales'],46.0); self.assertEqual(b2['gross_sales'],12.0)
        self.assertEqual(cashup_summary(self.c,date='2026-09-07',branch_id=1)['cash_sales'],46.0)
        self.assertEqual(cashup_summary(self.c,date='2026-09-07',branch_id=2)['cash_sales'],0.0)

if __name__=='__main__': unittest.main()
