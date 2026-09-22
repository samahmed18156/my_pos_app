import unittest

from core.migrations import run_migrations


class MigrationSmokeTests(unittest.TestCase):
    def test_migrations_entrypoint_runs(self):
        run_migrations()
        self.assertTrue(True)


if __name__ == '__main__':
    unittest.main()
