import unittest
from services.final_release import validate_entrypoint, validate_files, validate_version

class FinalReleaseTests(unittest.TestCase):
    def test_required_release_files_exist(self):
        self.assertEqual(validate_files(), [])

    def test_main_entrypoint_is_defined_before_guard(self):
        self.assertEqual(validate_entrypoint(), [])

    def test_release_version_is_present(self):
        self.assertEqual(validate_version(), [])

if __name__ == '__main__':
    unittest.main()
