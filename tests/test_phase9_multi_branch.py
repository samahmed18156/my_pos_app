import json, os, sqlite3, tempfile, unittest
from services import multi_branch_service as svc
from services import branch_stock_service

class Phase9Tests(unittest.TestCase):
    def setUp(self):
        self.db=tempfile.NamedTemporaryFile(suffix='.db',delete=False); self.db.close()
        self.c=sqlite3.connect(self.db.name)
        self.c.execute("CREATE TABLE branches(id INTEGER PRIMARY KEY,branch_name TEXT,branch_code TEXT,status TEXT)")
        self.c.execute("INSERT INTO branches VALUES(1,'Main Store','MAIN','Active'),(2,'North','NORTH','Active')")
        self.c.execute("CREATE TABLE products(barcode TEXT PRIMARY KEY,description TEXT,soh REAL DEFAULT 0)")
        self.c.execute("INSERT INTO products VALUES('A','Milk',10),('B','Bread',5)")
        self.c.execute("CREATE TABLE users(id INTEGER PRIMARY KEY)")
        branch_stock_service.DB_NAME=self.db.name; svc.DB_PATH=self.db.name if hasattr(svc,'DB_PATH') else None
        svc.ensure_schema_v9(self.c)
        self.c.execute("UPDATE branch_stock SET soh=0 WHERE branch_id=2")
        self.c.commit()
    def tearDown(self): self.c.close(); os.unlink(self.db.name)
    def test_overview_and_reconciliation(self):
        self.c.execute("UPDATE branch_stock SET soh=10 WHERE branch_id=1 AND barcode='A'")
        self.assertEqual(len(svc.branch_overview(self.c)),2)
        self.assertEqual(svc.reconciliation(self.c,1),[])
        self.c.execute("UPDATE products SET soh=11 WHERE barcode='A'")
        self.assertEqual(len(svc.reconciliation(self.c,1)),1)
    def test_export_import_is_staged_and_idempotent(self):
        self.c.execute("UPDATE branch_stock SET soh=10 WHERE branch_id=1 AND barcode='A'")
        self.c.commit()
        fd,path=tempfile.mkstemp(suffix='.json'); os.close(fd)
        try:
            batch=svc.export_bundle(self.c,1,path)
            self.assertTrue(batch)
            target=sqlite3.connect(self.db.name + '.target')
            target.execute("CREATE TABLE branches(id INTEGER PRIMARY KEY,branch_name TEXT,branch_code TEXT,status TEXT)")
            target.execute("INSERT INTO branches VALUES(1,'Main Store','MAIN','Active'),(2,'North','NORTH','Active')")
            target.execute("CREATE TABLE products(barcode TEXT PRIMARY KEY,description TEXT,soh REAL DEFAULT 0)")
            target.execute("INSERT INTO products VALUES('A','Milk',10),('B','Bread',5)")
            svc.ensure_schema_v9(target)
            target.commit()
            result=svc.import_bundle(target,path)
            self.assertEqual(result['rows'],2)
            self.assertEqual(result['conflicts'],0)
            dup=svc.import_bundle(target,path)
            self.assertTrue(dup['duplicate'])
            self.assertEqual(float(target.execute("SELECT soh FROM branch_stock WHERE branch_id=1 AND barcode='A'").fetchone()[0]),10)
            target.close(); os.unlink(self.db.name + '.target')
        finally: os.unlink(path)
    def test_transfer_history(self):
        branch_stock_service.transfer(self.c,1,2,'A',2,'admin'); self.c.commit()
        rows=svc.transfer_history(self.c,branch_id=2)
        self.assertEqual(len(rows),1); self.assertEqual(rows[0][1][:3], 'TRF')

if __name__=='__main__': unittest.main()
