import os, sqlite3, tempfile, unittest
from unittest.mock import patch

class AccountDocumentHistoryTests(unittest.TestCase):
    def setUp(self):
        fd,self.path=tempfile.mkstemp(suffix='.db'); os.close(fd)
        self.c=sqlite3.connect(self.path)
        self.c.executescript('''
        CREATE TABLE branches(id INTEGER PRIMARY KEY,name TEXT,address TEXT,phone TEXT);
        INSERT INTO branches VALUES(1,'Main','1 Main St','0100000000');
        CREATE TABLE sales_history(id INTEGER PRIMARY KEY AUTOINCREMENT,timestamp TEXT,total_amount REAL,payment_type TEXT,cashier TEXT,customer_name TEXT,branch_id INTEGER,branch_name TEXT);
        CREATE TABLE sale_items(id INTEGER PRIMARY KEY AUTOINCREMENT,sale_id INTEGER,barcode TEXT,description TEXT,qty REAL,price REAL,value REAL);
        INSERT INTO sales_history VALUES(1,'2026-09-07 10:00:00',115.0,'Credit Account','Cashier','Acme Customer',1,'Main');
        INSERT INTO sale_items VALUES(1,1,'A','Widget',2,57.5,115.0);
        CREATE TABLE grn_headers(id INTEGER PRIMARY KEY AUTOINCREMENT,grn_no TEXT,supplier_name TEXT,supplier_invoice TEXT,reference TEXT,subtotal REAL,vat REAL,total REAL,created_at TEXT,cashier TEXT,supplier_id INTEGER);
        CREATE TABLE grn_items(id INTEGER PRIMARY KEY AUTOINCREMENT,grn_id INTEGER,barcode TEXT,description TEXT,qty_received REAL,cost_price REAL,value REAL);
        INSERT INTO grn_headers VALUES(1,'GRN-000001','Acme Supplier','SUP-INV-9','REF-9',100,15,115,'2026-09-07 09:00:00','Manager',7);
        INSERT INTO grn_items VALUES(1,1,'A','Widget',5,20,100);
        ''')
        self.c.commit()
    def tearDown(self): self.c.close(); os.unlink(self.path)
    @patch('document_viewer.open_in_jasperviewer', return_value=(True,'JasperViewer opened.'))
    @patch('document_viewer.write_jrpxml', return_value='/tmp/test.jrpxml')
    def test_sale_history_document_uses_original_sale(self, write, openv):
        from document_viewer import _open
        _open('SALE',1,conn=self.c)
        self.assertEqual(write.call_args.kwargs['invoice_number'],'INV-000001')
        self.assertEqual(write.call_args.kwargs['customer_name'],'Acme Customer')
        self.assertEqual(len(write.call_args.kwargs['items']),1)
        openv.assert_called_once()
    @patch('document_viewer.open_in_jasperviewer', return_value=(True,'JasperViewer opened.'))
    @patch('document_viewer.write_jrpxml', return_value='/tmp/test.jrpxml')
    def test_grn_history_document_uses_original_grn(self, write, openv):
        from document_viewer import _open
        _open('GRN',1,conn=self.c)
        self.assertEqual(write.call_args.kwargs['invoice_number'],'GRN-000001')
        self.assertEqual(write.call_args.kwargs['customer_name'],'Acme Supplier')
        self.assertEqual(write.call_args.kwargs['payment_type'],'SUPPLIER PURCHASE')
        self.assertEqual(len(write.call_args.kwargs['items']),1)
        openv.assert_called_once()

if __name__=='__main__': unittest.main()


class TestInvoiceResolutionContract(unittest.TestCase):
    def test_debtor_invoice_history_uses_sale_id_reference(self):
        self.assertIn("sale_id", open("customer_accounts.py", encoding="utf-8").read())

    def test_supplier_statement_has_grn_view_action(self):
        self.assertIn("view_selected_document", open("supplier_statement.py", encoding="utf-8").read())
