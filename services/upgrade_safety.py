"""BKPOS Phase 75 — upgrade/data preservation safety checks.

Read-only checks for the release boundary.  These checks prove that a BKPOS
application update does not package or redirect the live user database and
that the installer continues to use a per-user application location.
"""
from __future__ import annotations

from pathlib import Path
import zipfile

from core.deployment_config import APP_NAME, APP_VERSION
from core.release_identity import INSTALLER_APP_ID

FORBIDDEN_DATA_FILES = {"pos_store.db"}
INSTALLER_FILES = ("packaging/windows/BKPOS.iss", "packaging/windows/BKPOS_Windows10.iss")


def validate_upgrade_safety(root: Path) -> list[str]:
    """Return upgrade-safety issues without changing any files."""
    root = Path(root)
    issues: list[str] = []

    for rel in INSTALLER_FILES:
        path = root / rel
        if not path.is_file():
            issues.append(f"Missing installer script: {rel}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "PrivilegesRequired=lowest" not in text:
            issues.append(f"Installer is not per-user: {rel}")
        if "DefaultDirName={localappdata}\\BKPOS" not in text:
            issues.append(f"Installer application path is not LocalAppData BKPOS: {rel}")
        if "pos_store.db" in text:
            issues.append(f"Installer script must not target live database: {rel}")
        if INSTALLER_APP_ID not in text:
            issues.append(f"Installer AppId mismatch: {rel}")
        if APP_VERSION not in text:
            issues.append(f"Installer version mismatch: {rel}")

    # A source/release tree must never contain the live user database.
    for path in root.rglob("*"):
        if path.is_file() and path.name.lower() in FORBIDDEN_DATA_FILES:
            issues.append(f"Live database present in release tree: {path.relative_to(root)}")

    return sorted(set(issues))


def validate_upgrade_zip(zip_path: str | Path) -> list[str]:
    """Inspect a release ZIP without extracting or modifying it."""
    path = Path(zip_path)
    if not path.is_file():
        return [f"Release ZIP not found: {path}"]
    issues: list[str] = []
    try:
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                normalized = name.replace("\\", "/").lower()
                if normalized.rsplit("/", 1)[-1] == "pos_store.db":
                    issues.append(f"ZIP contains live database: {name}")
                if (normalized.endswith(".db") or normalized.endswith(".sqlite") or normalized.endswith(".sqlite3")) and "backup" not in normalized:
                    issues.append(f"ZIP contains database file: {name}")
            names = [n.replace("\\", "/").lower() for n in zf.namelist()]
            for required in INSTALLER_FILES:
                if not any(n.endswith(required.lower()) for n in names):
                    issues.append(f"ZIP missing installer script: {required}")
    except zipfile.BadZipFile:
        issues.append(f"Invalid ZIP archive: {path}")
    return sorted(set(issues))


def upgrade_safety_summary(root: Path, zip_path: str | Path | None = None) -> dict[str, object]:
    tree_issues = validate_upgrade_safety(root)
    zip_issues = validate_upgrade_zip(zip_path) if zip_path else []
    return {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "tree_ok": not tree_issues,
        "zip_ok": not zip_issues if zip_path else None,
        "issues": tree_issues + zip_issues,
    }
