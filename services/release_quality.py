"""BKPOS release/codebase quality checks.

Read-only helpers used before creating a distributable release.  They do not
modify the application database, configuration, or source tree.
"""
from __future__ import annotations

import ast
import hashlib
import os
from pathlib import Path
from dataclasses import dataclass


@dataclass(frozen=True)
class QualityIssue:
    severity: str
    path: str
    message: str


FORBIDDEN_RELEASE_NAMES = {"pos_store.db", "pos_store.sqlite", "pos_store.sqlite3"}
FORBIDDEN_DIR_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".idea", "build", "dist", "output", "generated", "logs", "backups", "receipts", "diagnostics", "runtime"}
REQUIRED_RELEASE_FILES = {"app.py", "database.py", "VERSION.txt", "RELEASE_VERSION.txt", "REQUIREMENTS.txt"}


def compile_python_tree(root: str | os.PathLike[str]) -> list[QualityIssue]:
    root_path = Path(root)
    issues: list[QualityIssue] = []
    for path in sorted(root_path.rglob("*.py"), key=lambda p: str(p.relative_to(root_path))):
        if any(part in FORBIDDEN_DIR_NAMES for part in path.parts):
            continue
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError) as exc:
            issues.append(QualityIssue("ERROR", str(path.relative_to(root_path)), f"Python parse failed: {exc}"))
    return issues


def scan_release_tree(root: str | os.PathLike[str]) -> list[QualityIssue]:
    root_path = Path(root)
    issues: list[QualityIssue] = []
    for path in root_path.rglob("*"):
        rel = path.relative_to(root_path)
        if path.is_dir() and path.name in FORBIDDEN_DIR_NAMES:
            issues.append(QualityIssue("ERROR", str(rel), "Development cache directory must not be released"))
            continue
        if path.is_file() and (path.name in FORBIDDEN_RELEASE_NAMES or path.suffix.lower() in {".pyc", ".pyo"}):
            issues.append(QualityIssue("ERROR", str(rel), "Runtime/database artifact must not be packaged"))
    return issues


def missing_required_files(root: str | os.PathLike[str]) -> list[str]:
    root_path = Path(root)
    return sorted(name for name in REQUIRED_RELEASE_FILES if not (root_path / name).is_file())


def duplicate_content_files(root: str | os.PathLike[str], max_bytes: int = 2_000_000) -> list[tuple[str, str]]:
    """Find exact duplicate source files without flagging known legacy modules."""
    root_path = Path(root)
    hashes: dict[str, str] = {}
    duplicates: list[tuple[str, str]] = []
    for path in sorted(root_path.rglob("*.py"), key=lambda p: str(p.relative_to(root_path))):
        if path.stat().st_size > max_bytes or any(part in FORBIDDEN_DIR_NAMES for part in path.parts):
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        rel = str(path.relative_to(root_path))
        if digest in hashes:
            pair = tuple(sorted((hashes[digest], rel)))
            duplicates.append(pair)
        else:
            hashes[digest] = rel
    return sorted(set(duplicates))


def summarize(root: str | os.PathLike[str]) -> dict[str, object]:
    root_path = Path(root)
    python_files = [p for p in root_path.rglob("*.py") if not any(part in FORBIDDEN_DIR_NAMES for part in p.parts)]
    issues = compile_python_tree(root_path) + scan_release_tree(root_path)
    missing = missing_required_files(root_path)
    duplicates = duplicate_content_files(root_path)
    return {
        "python_files": len(python_files),
        "issues": issues,
        "missing_required_files": missing,
        "duplicate_content_files": duplicates,
        "ready": not issues and not missing,
    }
