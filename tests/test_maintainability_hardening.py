import ast
import sqlite3
from pathlib import Path
import unittest

from core.document_numbers import next_document_number

ROOT = Path(__file__).resolve().parents[1]

class MaintainabilityHardeningTests(unittest.TestCase):
    def test_document_numbers_are_monotonic(self):
        conn = sqlite3.connect(':memory:')
        conn.execute('CREATE TABLE grn_headers(id INTEGER PRIMARY KEY AUTOINCREMENT, grn_no TEXT)')
        conn.execute('CREATE TABLE stock_transfers(id INTEGER PRIMARY KEY AUTOINCREMENT, transfer_no TEXT)')
        self.assertEqual(next_document_number(conn, 'grn', 'GRN'), 'GRN-000001')
        self.assertEqual(next_document_number(conn, 'grn', 'GRN'), 'GRN-000002')
        self.assertEqual(next_document_number(conn, 'transfer', 'TRF'), 'TRF-000001')
        conn.close()

    def test_no_pass_only_exception_handlers_in_application(self):
        offenders = []
        for path in ROOT.rglob('*.py'):
            if 'tests' in path.parts or '__pycache__' in path.parts:
                continue
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler) and len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                    offenders.append(f'{path}:{node.lineno}')
        self.assertEqual(offenders, [])

if __name__ == '__main__':
    unittest.main()
