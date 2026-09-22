import tempfile
from pathlib import Path
import unittest

from services.release_quality import (
    compile_python_tree,
    duplicate_content_files,
    missing_required_files,
    scan_release_tree,
    summarize,
)


class TestPhase58ReleaseQuality(unittest.TestCase):
    def test_clean_tree_is_ready(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ("app.py", "database.py", "VERSION.txt", "RELEASE_VERSION.txt", "REQUIREMENTS.txt"):
                (root / name).write_text("# ok\n", encoding="utf-8")
            (root / "core").mkdir()
            (root / "core" / "x.py").write_text("value = 1\n", encoding="utf-8")
            result = summarize(root)
            self.assertTrue(result["ready"])
            self.assertEqual(result["issues"], [])

    def test_forbidden_database_and_cache_are_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "pos_store.db").write_bytes(b"x")
            (root / "__pycache__").mkdir()
            (root / "__pycache__" / "x.pyc").write_bytes(b"x")
            issues = scan_release_tree(root)
            self.assertGreaterEqual(len(issues), 2)
            self.assertTrue(any("database" in i.message.lower() or "runtime" in i.message.lower() for i in issues))

    def test_missing_required_files(self):
        with tempfile.TemporaryDirectory() as td:
            missing = missing_required_files(td)
            self.assertEqual(set(missing), {"app.py", "database.py", "VERSION.txt", "RELEASE_VERSION.txt", "REQUIREMENTS.txt"})

    def test_syntax_error_detected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "bad.py").write_text("def broken(:\n", encoding="utf-8")
            issues = compile_python_tree(root)
            self.assertEqual(len(issues), 1)
            self.assertEqual(issues[0].severity, "ERROR")

    def test_exact_duplicate_content_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.py").write_text("same = 1\n", encoding="utf-8")
            (root / "b.py").write_text("same = 1\n", encoding="utf-8")
            self.assertEqual(duplicate_content_files(root), [("a.py", "b.py")])


if __name__ == "__main__":
    unittest.main()
