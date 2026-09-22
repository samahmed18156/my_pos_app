"""BKPOS 10.0.0 Gold Release gate.

Read-only validation of the final production release tree. It does not open,
migrate, replace, or modify the live BKPOS database or installed executable.
"""
from __future__ import annotations

import compileall
import zipfile
from pathlib import Path

APP_NAME = "BKPOS"
APP_VERSION = "10.0.0"
EXE_VERSION = "10.0.0.0"

REQUIRED = (
    "app.py",
    "database.py",
    "VERSION.txt",
    "RELEASE_VERSION.txt",
    "core/release_identity.py",
    "core/deployment_config.py",
    "packaging/windows/BKPOS.iss",
    "packaging/windows/BKPOS_Windows10.iss",
    "packaging/windows/BKPOS.spec",
    "packaging/windows/BKPOS_Windows10.spec",
    "packaging/windows/BKPOS_version_info.txt",
    "services/gold_release_gate.py",
)
FORBIDDEN_NAMES = {
    "pos_store.db", "pos_store.sqlite", "pos_store.sqlite3",
}
FORBIDDEN_DIRS = {
    ".idea", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "build", "dist", "output", "generated", "logs", "backups", "receipts",
    "diagnostics", "runtime",
}
FORBIDDEN_SUFFIXES = {".pyc", ".pyo"}


def validate_tree(root: Path) -> list[str]:
    issues: list[str] = []
    for rel in REQUIRED:
        if not (root / rel).is_file():
            issues.append(f"missing gold-release file: {rel}")
    if (root / "VERSION.txt").is_file():
        text = (root / "VERSION.txt").read_text(encoding="utf-8").strip()
        if text != f"{APP_NAME} {APP_VERSION}":
            issues.append("VERSION.txt is not the final Gold Release identity.")
    if (root / "RELEASE_VERSION.txt").is_file():
        text = (root / "RELEASE_VERSION.txt").read_text(encoding="utf-8").strip()
        if text != f"{APP_NAME} {APP_VERSION} Gold Release":
            issues.append("RELEASE_VERSION.txt is not marked Gold Release.")
    for rel in ("core/release_identity.py", "core/deployment_config.py"):
        p = root / rel
        if p.is_file() and 'APP_VERSION = "10.0.0"' not in p.read_text(encoding="utf-8"):
            issues.append(f"{rel} does not declare Gold Release version 10.0.0.")
    for rel in ("packaging/windows/BKPOS.iss", "packaging/windows/BKPOS_Windows10.iss"):
        p = root / rel
        if p.is_file():
            t = p.read_text(encoding="utf-8")
            if '#define MyAppVersion "10.0.0"' not in t:
                issues.append(f"{rel} has the wrong installer version.")
            if "PrivilegesRequired=lowest" not in t:
                issues.append(f"{rel} is not per-user.")
            if "SetupIconFile=" in t:
                issues.append(f"{rel} contains an external setup-icon dependency.")
    v = root / "packaging/windows/BKPOS_version_info.txt"
    if v.is_file():
        t = v.read_text(encoding="utf-8")
        for needle in ("StringStruct('ProductName','BKPOS')", "StringStruct('ProductVersion','10.0.0.0')", "StringStruct('OriginalFilename','BKPOS.exe')"):
            if needle not in t:
                issues.append(f"version metadata missing: {needle}")
    for p in root.rglob("*"):
        rel = p.relative_to(root)
        if any(part.lower() in {x.lower() for x in FORBIDDEN_DIRS} for part in rel.parts):
            issues.append(f"forbidden release directory/artifact: {rel}")
            continue
        if p.is_file() and (p.name.lower() in {x.lower() for x in FORBIDDEN_NAMES} or p.suffix.lower() in FORBIDDEN_SUFFIXES):
            issues.append(f"forbidden release artifact: {rel}")
    return issues


def validate_zip(path: Path) -> list[str]:
    if not path.is_file():
        return ["gold release ZIP is missing"]
    issues: list[str] = []
    with zipfile.ZipFile(path) as zf:
        bad = zf.testzip()
        if bad:
            issues.append(f"ZIP integrity failure: {bad}")
        names = zf.namelist()
        for name in names:
            base = Path(name).name
            if base == "pos_store.db" or base.endswith(".pyc") or "__pycache__" in name:
                issues.append(f"forbidden artifact in Gold ZIP: {name}")
        if not any(name.endswith("VERSION.txt") for name in names):
            issues.append("Gold ZIP missing VERSION.txt")
        if not any(name.endswith("RELEASE_VERSION.txt") for name in names):
            issues.append("Gold ZIP missing RELEASE_VERSION.txt")
    return issues


def run_gold_release_gate(root: Path) -> list[str]:
    issues = validate_tree(root)
    if not compileall.compile_dir(str(root), quiet=1, maxlevels=10):
        issues.append("Python compilation failed")
    return issues
