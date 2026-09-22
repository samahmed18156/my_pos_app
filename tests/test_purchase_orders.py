import os,sqlite3,tempfile,unittest
from services.purchase_order_service import ensure_schema,create_purchase_order,set_status,update_receipts_for_po
class PurchaseOrderTests(unittest.TestCase):
 def setUp(self):
  fd,self.path=tempfile.mkstemp(suffix='.db');os.close(fd);self.c=sqlite3.connect(self.path)
  self.c.executescript("CREATE TABLE products(barcode TEXT PRIMARY KEY,description TEXT,cost_price REAL,soh REAL); INSERT INTO products VALUES('A','Widget',10,5); CREATE TABLE accounts(id INTEGER PRIMARY KEY,name TEXT,type TEXT,supplier_account_no TEXT); INSERT INTO accounts VALUES(7,'Acme','Supplier','SUP-007'); CREATE TABLE grn_headers(id INTEGER PRIMARY KEY,po_no TEXT); CREATE TABLE grn_items(id INTEGER PRIMARY KEY,grn_id INTEGER,barcode TEXT,qty_received REAL);")
  ensure_schema(self.c);self.c.commit()
 def tearDown(self):self.c.close();os.unlink(self.path)
 def test_create_po_does_not_change_stock_or_liability(self):
  r=create_purchase_order(self.c,supplier_id=7,supplier_account='SUP-007',supplier_name='Acme',items=[{'barcode':'A','qty':10,'cost':12}],created_by='manager');self.c.commit()
  self.assertEqual(r['po_no'],'PO-000001');self.assertEqual(self.c.execute('SELECT soh FROM products WHERE barcode="A"').fetchone()[0],5);self.assertEqual(self.c.execute('SELECT status,total FROM purchase_orders').fetchone(),('DRAFT',120))
 def test_status_ordered(self):
  r=create_purchase_order(self.c,supplier_id=7,supplier_account='SUP-007',supplier_name='Acme',items=[{'barcode':'A','qty':2,'cost':12}]);set_status(self.c,r['po_id'],'ORDERED');self.assertEqual(self.c.execute('SELECT status FROM purchase_orders').fetchone()[0],'ORDERED')
 def test_receipt_updates_partial_and_full(self):
  r=create_purchase_order(self.c,supplier_id=7,supplier_account='SUP-007',supplier_name='Acme',items=[{'barcode':'A','qty':10,'cost':12}]);self.c.execute('INSERT INTO grn_headers(id,po_no) VALUES(1,?)',(r['po_no'],));self.c.execute("INSERT INTO grn_items VALUES(1,1,'A',4)");update_receipts_for_po(self.c,r['po_no']);self.assertEqual(self.c.execute('SELECT status,received_qty FROM purchase_orders JOIN purchase_order_items ON purchase_orders.id=purchase_order_items.po_id').fetchone(),('PARTIALLY RECEIVED',4));self.c.execute("INSERT INTO grn_items VALUES(2,1,'A',6)");update_receipts_for_po(self.c,r['po_no']);self.assertEqual(self.c.execute('SELECT status,received_qty FROM purchase_orders JOIN purchase_order_items ON purchase_orders.id=purchase_order_items.po_id').fetchone(),('FULLY RECEIVED',10))
if __name__=='__main__':unittest.main()
