"""Final production-release validation for BKPOS.

Read-only checks intended for release packaging. No business data is modified.
"""
from __future__ import annotations
import ast
import compileall
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REQUIRED_FILES = ("app.py", "database.py", "VERSION.txt", "release_check.py", "run_tests.py")
REQUIRED_DOCS = ("PHASE18_BACKUP_DISASTER_RECOVERY.md", "PHASE19_PERFORMANCE_SCALABILITY.md")


def validate_files() -> list[str]:
    missing = [name for name in REQUIRED_FILES + REQUIRED_DOCS if not (BASE_DIR / name).is_file()]
    return [f"missing file: {name}" for name in missing]


def validate_entrypoint() -> list[str]:
    path = BASE_DIR / "app.py"
    if not path.is_file():
        return ["app.py missing"]
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    main_defs = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"]
    guards = [n for n in tree.body if isinstance(n, ast.If) and isinstance(n.test, ast.Compare)
              and any(isinstance(x, ast.Name) and x.id == "__name__" for x in [n.test.left])]
    if not main_defs:
        return ["app.py main() definition missing"]
    if not guards:
        return ["app.py __main__ guard missing"]
    if tree.body.index(guards[-1]) < tree.body.index(main_defs[-1]):
        return ["app.py invokes __main__ before main() definition"]
    return []


def validate_python_tree() -> list[str]:
    ok = compileall.compile_dir(str(BASE_DIR), quiet=1, maxlevels=10)
    return [] if ok else ["Python compilation failed"]


def validate_version() -> list[str]:
    text = (BASE_DIR / "VERSION.txt").read_text(encoding="utf-8").strip()
    return [] if text else ["VERSION.txt is empty"]


def run_all() -> dict:
    problems = validate_files() + validate_entrypoint() + validate_python_tree() + validate_version()
    return {"ok": not problems, "problems": problems}
