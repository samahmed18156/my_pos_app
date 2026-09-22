import os
import sqlite3
import tempfile
import unittest

import login
import permissions
import security
from services import branch_stock_service as branch_stock
from services import stock_service


class TempDBMixin:
    def make_db(self):
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        return path


class SecurityEdgeTests(unittest.TestCase):
    def test_hashes_use_unique_salts(self):
        a = security.hash_password("same-password")
        b = security.hash_password("same-password")
        self.assertNotEqual(a, b)
        self.assertTrue(security.verify_password("same-password", a))
        self.assertTrue(security.verify_password("same-password", b))

    def test_malformed_hashes_fail_closed(self):
        for value in ["", "plaintext", "pbkdf2_sha256$bad", "pbkdf2_sha256$310000$zz$zz"]:
            self.assertFalse(security.verify_password("anything", value))

    def test_empty_password_cannot_be_hashed(self):
        with self.assertRaises(ValueError):
            security.hash_password("")


class LoginIntegrationTests(TempDBMixin, unittest.TestCase):
    def setUp(self):
        self.db = self.make_db()
        self.old_login_db = login.DB_NAME
        self.old_perm_db = permissions.DB_NAME
        login.DB_NAME = self.db
        permissions.DB_NAME = self.db
        c = sqlite3.connect(self.db)
        c.execute("""CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL DEFAULT '',
            password_hash TEXT,
            full_name TEXT,
            role TEXT DEFAULT 'cashier',
            can_edit_price INTEGER DEFAULT 0,
            can_edit_qty INTEGER DEFAULT 1,
            can_delete_items INTEGER DEFAULT 1,
            can_view_reports INTEGER DEFAULT 1,
            can_access_stock INTEGER DEFAULT 0,
            can_access_debtors INTEGER DEFAULT 0,
            can_access_creditors INTEGER DEFAULT 0,
            can_access_utility INTEGER DEFAULT 0,
            branch_id INTEGER DEFAULT 1
        )""")
        c.execute("INSERT INTO users(username,password,password_hash,full_name,role) VALUES(?,?,?,?,?)",
                  ("alice", "", security.hash_password("secret"), "Alice", "Cashier"))
        c.commit(); c.close()

    def tearDown(self):
        login.DB_NAME = self.old_login_db
        permissions.DB_NAME = self.old_perm_db

    def test_correct_credentials_return_user(self):
        result = login._check_credentials("alice", "secret")
        self.assertEqual(result["username"], "alice")
        self.assertEqual(result["role"], "Cashier")

    def test_wrong_password_is_rejected(self):
        self.assertIsNone(login._check_credentials("alice", "wrong"))

    def test_plaintext_column_is_never_used_when_hash_exists(self):
        c = sqlite3.connect(self.db)
        c.execute("UPDATE users SET password='secret' WHERE username='alice'")
        c.commit(); c.close()
        # The hash is deliberately changed to a different password. The
        # legacy plaintext value must not become an authentication fallback.
        c = sqlite3.connect(self.db)
        c.execute("UPDATE users SET password_hash=? WHERE username='alice'",
                  (security.hash_password("different-secret"),))
        c.commit(); c.close()
        self.assertIsNone(login._check_credentials("alice", "secret"))

    def test_unknown_user_is_rejected(self):
        self.assertIsNone(login._check_credentials("nobody", "secret"))

    def test_legacy_plaintext_is_migrated_before_authentication(self):
        c = sqlite3.connect(self.db)
        c.execute("INSERT INTO users(username,password,password_hash,full_name,role) VALUES(?,?,?,?,?)",
                  ("legacy", "oldpass", "", "Legacy", "Cashier"))
        c.commit(); c.close()
        # Authentication performs the migration first, but does not accept
        # plaintext credentials as a fallback.
        self.assertIsNotNone(login._check_credentials("legacy", "oldpass"))
        row = sqlite3.connect(self.db).execute(
            "SELECT password,password_hash FROM users WHERE username='legacy'"
        ).fetchone()
        self.assertEqual(row[0], "")
        self.assertTrue(security.verify_password("oldpass", row[1]))


class BranchStockTests(TempDBMixin, unittest.TestCase):
    def setUp(self):
        self.db = self.make_db()
        self.conn = sqlite3.connect(self.db)
        self.conn.executescript("""
            CREATE TABLE branches(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
            CREATE TABLE products(
                barcode TEXT PRIMARY KEY,
                description TEXT NOT NULL,
                selling_price REAL NOT NULL,
                cost_price REAL DEFAULT 0,
                soh REAL DEFAULT 0
            );
            INSERT INTO branches VALUES(1,'Main Store'),(2,'Branch 2'),(3,'Branch 3');
            INSERT INTO products VALUES('100','Coffee',20,10,10);
            INSERT INTO products VALUES('200','Tea',15,7,0);
        """)
        self.conn.commit()
        self.old_db = branch_stock.DB_NAME
        branch_stock.DB_NAME = self.db
        branch_stock.ensure_schema(self.conn)
        self.conn.commit()

    def tearDown(self):
        branch_stock.DB_NAME = self.old_db
        self.conn.close()

    def branch_qty(self, bid, code='100'):
        return branch_stock.get_branch_soh(self.conn, bid, code)

    def global_qty(self, code='100'):
        return self.conn.execute("SELECT soh FROM products WHERE barcode=?", (code,)).fetchone()[0]

    def test_initial_stock_is_seeded_to_main_branch_only(self):
        self.assertEqual(self.branch_qty(1), 10)
        self.assertEqual(self.branch_qty(2), 0)
        self.assertEqual(self.branch_qty(3), 0)

    def test_sale_decrements_branch_and_global_stock(self):
        before, after = branch_stock.change_stock(self.conn, 1, '100', -3, expected_before=10)
        self.assertEqual((before, after), (10.0, 7.0))
        self.assertEqual(self.branch_qty(1), 7)
        self.assertEqual(self.global_qty(), 7)

    def test_receipt_adds_stock_to_branch_and_global(self):
        before, after = branch_stock.change_stock(self.conn, 2, '200', 5)
        self.assertEqual((before, after), (0.0, 5.0))
        self.assertEqual(self.branch_qty(2, '200'), 5)
        self.assertEqual(self.conn.execute("SELECT soh FROM products WHERE barcode='200'").fetchone()[0], 5)

    def test_insufficient_branch_stock_is_rejected_without_changes(self):
        with self.assertRaises(ValueError):
            branch_stock.change_stock(self.conn, 2, '100', -1)
        self.assertEqual(self.branch_qty(2), 0)
        self.assertEqual(self.global_qty(), 10)

    def test_expected_before_detects_concurrent_change(self):
        with self.assertRaises(ValueError):
            branch_stock.change_stock(self.conn, 1, '100', -1, expected_before=99)
        self.assertEqual(self.branch_qty(1), 10)
        self.assertEqual(self.global_qty(), 10)

    def test_unknown_product_is_rejected(self):
        with self.assertRaises(ValueError):
            branch_stock.change_stock(self.conn, 1, '999', 1)

    def test_zero_delta_is_a_noop(self):
        result = branch_stock.change_stock(self.conn, 1, '100', 0)
        self.assertEqual(result, (10.0, 10.0))
        self.assertEqual(self.global_qty(), 10)

    def test_same_branch_transfer_is_rejected(self):
        with self.assertRaises(ValueError):
            branch_stock.transfer(self.conn, 1, 1, '100', 1)
        self.assertEqual(self.global_qty(), 10)

    def test_negative_transfer_is_rejected(self):
        with self.assertRaises(ValueError):
            branch_stock.transfer(self.conn, 1, 2, '100', 0)
        with self.assertRaises(ValueError):
            branch_stock.transfer(self.conn, 1, 2, '100', -1)

    def test_transfer_preserves_global_total(self):
        no, before, after = branch_stock.transfer(self.conn, 1, 2, '100', 4, 'alice')
        self.assertEqual(no, 'TRF-000001')
        self.assertEqual((before, after), (10.0, 6.0))
        self.assertEqual(self.branch_qty(1), 6)
        self.assertEqual(self.branch_qty(2), 4)
        self.assertEqual(self.global_qty(), 10)
        row = self.conn.execute("SELECT from_branch,to_branch,barcode,qty,cashier,status FROM stock_transfers").fetchone()
        self.assertEqual(row, (1, 2, '100', 4.0, 'alice', 'POSTED'))

    def test_transfer_insufficient_stock_changes_nothing(self):
        with self.assertRaises(ValueError):
            branch_stock.transfer(self.conn, 2, 3, '100', 1, 'alice')
        self.assertEqual(self.branch_qty(2), 0)
        self.assertEqual(self.branch_qty(3), 0)
        self.assertEqual(self.global_qty(), 10)
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM stock_transfers").fetchone()[0], 0)

    def test_multiple_transfers_get_unique_numbers(self):
        branch_stock.transfer(self.conn, 1, 2, '100', 2)
        branch_stock.transfer(self.conn, 1, 3, '100', 1)
        nums = [r[0] for r in self.conn.execute("SELECT transfer_no FROM stock_transfers ORDER BY id")]
        self.assertEqual(nums, ['TRF-000001', 'TRF-000002'])

    def test_rollback_restores_branch_and_global_stock(self):
        self.conn.execute('BEGIN')
        branch_stock.change_stock(self.conn, 1, '100', -2)
        self.conn.rollback()
        self.assertEqual(self.branch_qty(1), 10)
        self.assertEqual(self.global_qty(), 10)


class StockMovementTests(TempDBMixin, unittest.TestCase):
    def setUp(self):
        self.db = self.make_db()
        self.conn = sqlite3.connect(self.db)
        self.conn.executescript("""
            CREATE TABLE products(barcode TEXT PRIMARY KEY, description TEXT, cost_price REAL, soh REAL);
            CREATE TABLE stock_movements(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                barcode TEXT, description TEXT, movement_type TEXT, qty REAL,
                qty_before REAL, qty_after REAL, cost_price REAL,
                reference TEXT, reason TEXT, cashier TEXT
            );
            INSERT INTO products VALUES('100','Coffee',10,8);
        """)
        self.conn.commit()
        self.old_path = stock_service.DB_PATH
        stock_service.DB_PATH = self.db

    def tearDown(self):
        stock_service.DB_PATH = self.old_path
        self.conn.close()

    def test_movement_can_join_caller_transaction(self):
        self.conn.execute('BEGIN')
        stock_service.record_stock_movement('100', 'SALE', -2, reference='SALE #1',
                                            description='Coffee', qty_before=8, qty_after=6,
                                            cost_price=10, cashier='alice', conn=self.conn)
        self.conn.rollback()
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM stock_movements').fetchone()[0], 0)

    def test_movement_commits_when_service_owns_connection(self):
        stock_service.record_stock_movement('100', 'SALE', -2, reference='SALE #1',
                                            description='Coffee', qty_before=8, qty_after=6,
                                            cost_price=10, cashier='alice')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM stock_movements').fetchone()[0], 1)

    def test_derived_state_uses_current_product_stock(self):
        stock_service.record_stock_movement('100', 'GRN', 3)
        row = self.conn.execute("SELECT qty,qty_before,qty_after,description,cost_price FROM stock_movements").fetchone()
        self.assertEqual(row, (3.0, 5.0, 8.0, 'Coffee', 10.0))


class SchemaSafetyTests(TempDBMixin, unittest.TestCase):
    def test_branch_schema_creation_is_idempotent(self):
        path = self.make_db()
        c = sqlite3.connect(path)
        c.execute("CREATE TABLE branches(id INTEGER PRIMARY KEY, name TEXT)")
        c.execute("CREATE TABLE products(barcode TEXT PRIMARY KEY, description TEXT, soh REAL, cost_price REAL)")
        c.execute("INSERT INTO branches VALUES(1,'Main')")
        c.execute("INSERT INTO products VALUES('1','Item',4,2)")
        c.commit()
        branch_stock.ensure_schema(c)
        branch_stock.ensure_schema(c)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM branch_stock").fetchone()[0], 1)
        c.close()

    def test_product_data_survives_branch_schema_setup(self):
        path = self.make_db()
        c = sqlite3.connect(path)
        c.execute("CREATE TABLE branches(id INTEGER PRIMARY KEY, name TEXT)")
        c.execute("CREATE TABLE products(barcode TEXT PRIMARY KEY, description TEXT, soh REAL, cost_price REAL)")
        c.execute("INSERT INTO branches VALUES(1,'Main')")
        c.execute("INSERT INTO products VALUES('X','Important item',17,9)")
        c.commit()
        branch_stock.ensure_schema(c)
        row = c.execute("SELECT barcode,description,soh,cost_price FROM products").fetchone()
        self.assertEqual(row, ('X','Important item',17.0,9.0))
        c.close()


if __name__ == '__main__':
    unittest.main()
