"""BKPOS Phase 65 — final production audit.

Read-only release gate covering source integrity, release artifacts, packaging
configuration, version metadata, and deployment policy. It intentionally does
not modify the application database or the installed BKPOS application.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from core.deployment_config import APP_NAME, APP_VERSION


FORBIDDEN_NAMES = {"pos_store.db", "pos_store.sqlite", "pos_store.sqlite3"}
FORBIDDEN_SUFFIXES = {".pyc", ".pyo"}
FORBIDDEN_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
REQUIRED_FILES = {"app.py", "database.py", "VERSION.txt", "RELEASE_VERSION.txt", "REQUIREMENTS.txt"}
PACKAGING_DIR = Path("packaging") / "windows"

@dataclass(frozen=True)
class AuditCheck:
    name: str
    status: str
    message: str

    @property
    def ok(self) -> bool:
        return self.status == "PASS"


def _pass(name: str, message: str) -> AuditCheck:
    return AuditCheck(name, "PASS", message)


def _fail(name: str, message: str) -> AuditCheck:
    return AuditCheck(name, "FAIL", message)


def audit_source_tree(root: str | Path) -> list[AuditCheck]:
    root = Path(root)
    checks: list[AuditCheck] = []
    parse_errors: list[str] = []
    artifacts: list[str] = []
    for path in root.rglob("*"):
        rel = path.relative_to(root)
        if path.is_dir() and path.name in FORBIDDEN_DIRS:
            continue
        if not path.is_file():
            continue
        if any(part in FORBIDDEN_DIRS for part in path.parts):
            continue
        if path.name in FORBIDDEN_NAMES or path.suffix.lower() in FORBIDDEN_SUFFIXES:
            artifacts.append(str(rel))
        if path.suffix.lower() == ".py" and not any(part in FORBIDDEN_DIRS for part in path.parts):
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (SyntaxError, UnicodeDecodeError) as exc:
                parse_errors.append(f"{rel}: {exc}")
    checks.append(_pass("python_syntax", f"All release Python files parse successfully.") if not parse_errors else _fail("python_syntax", "; ".join(parse_errors[:5])))
    checks.append(_pass("release_artifacts", "No database or Python bytecode artifacts are present in the source tree.") if not artifacts else _fail("release_artifacts", "; ".join(artifacts[:10])))
    missing = sorted(name for name in REQUIRED_FILES if not (root / name).is_file())
    checks.append(_pass("required_files", "All required release metadata files are present.") if not missing else _fail("required_files", "Missing: " + ", ".join(missing)))
    return checks


def audit_packaging(root: str | Path) -> list[AuditCheck]:
    root = Path(root)
    pkg = root / PACKAGING_DIR
    expected = ["BKPOS.spec", "BKPOS.iss", "BKPOS_Windows10.spec", "BKPOS_Windows10.iss", "MAKE_BKPOS_INSTALLER.bat", "CREATE_BKPOS_DESKTOP_SHORTCUT.bat"]
    missing = [name for name in expected if not (pkg / name).is_file()]
    checks = [_pass("windows_packaging", "BKPOS Windows packaging definitions are present.") if not missing else _fail("windows_packaging", "Missing: " + ", ".join(missing))]
    legacy = []
    for path in pkg.glob("*"):
        if path.is_file() and re.search(r"mipos", path.name, re.I):
            legacy.append(path.name)
    checks.append(_pass("packaging_branding", "Windows packaging filenames contain no legacy MiPOS branding.") if not legacy else _fail("packaging_branding", "Legacy packaging files: " + ", ".join(legacy)))
    return checks


def audit_versions(root: str | Path) -> list[AuditCheck]:
    root = Path(root)
    version_text = (root / "VERSION.txt").read_text(encoding="utf-8").strip()
    release_text = (root / "RELEASE_VERSION.txt").read_text(encoding="utf-8").strip()
    checks = []
    checks.append(_pass("version_metadata", "Version metadata files are non-empty.") if version_text and release_text else _fail("version_metadata", "VERSION.txt or RELEASE_VERSION.txt is empty."))
    checks.append(_pass("application_identity", f"Application identity is {APP_NAME} {APP_VERSION}.") if APP_NAME == "BKPOS" else _fail("application_identity", f"Unexpected application identity: {APP_NAME}"))
    return checks


def run_final_audit(root: str | Path) -> dict:
    root = Path(root)
    checks = audit_source_tree(root) + audit_packaging(root) + audit_versions(root)
    return {"ok": all(c.ok for c in checks), "checks": checks, "app_name": APP_NAME, "app_version": APP_VERSION}


def format_audit(audit: dict) -> str:
    lines = ["BKPOS Phase 65 — Final Production Audit", "=" * 42]
    for check in audit["checks"]:
        lines.append(f"{check.status}: {check.name} — {check.message}")
    lines.append("")
    lines.append("FINAL STATUS: " + ("PASS" if audit["ok"] else "FAIL"))
    return "\n".join(lines)
