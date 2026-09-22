"""BKPOS Phase 73 — single source of truth for release identity."""
from __future__ import annotations

from pathlib import Path

APP_NAME = "BKPOS"
APP_VERSION = "10.0.0"
EXE_VERSION = "10.0.0.0"
INSTALLER_APP_ID = "{A3B2C1D0-6F54-4E21-9A87-100000000001}"

BASE_DIR = Path(__file__).resolve().parents[1]


def release_identity() -> dict[str, str]:
    return {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "exe_version": EXE_VERSION,
        "installer_app_id": INSTALLER_APP_ID,
    }


def validate_release_identity() -> list[str]:
    """Read-only consistency checks across release metadata and installers."""
    issues: list[str] = []
    version_text = (BASE_DIR / "VERSION.txt").read_text(encoding="utf-8").strip()
    release_text = (BASE_DIR / "RELEASE_VERSION.txt").read_text(encoding="utf-8").strip()
    if APP_NAME not in version_text:
        issues.append("VERSION.txt is missing BKPOS identity.")
    if APP_VERSION not in version_text:
        issues.append("VERSION.txt is missing the current application version.")
    if APP_NAME not in release_text:
        issues.append("RELEASE_VERSION.txt is missing BKPOS identity.")
    if APP_VERSION not in release_text:
        issues.append("RELEASE_VERSION.txt is missing the current application version.")

    for name in ("BKPOS.iss", "BKPOS_Windows10.iss"):
        text = (BASE_DIR / "packaging" / "windows" / name).read_text(encoding="utf-8")
        if f'#define MyAppVersion "{APP_VERSION}"' not in text:
            issues.append(f"{name} has a mismatched installer version.")
        if "PrivilegesRequired=lowest" not in text:
            issues.append(f"{name} is not configured for per-user installation.")
        if "SetupIconFile=" in text:
            issues.append(f"{name} references an external setup icon that must exist in the release tree.")
    spec_dir = BASE_DIR / "packaging" / "windows"
    for name in ("BKPOS.spec", "BKPOS_Windows10.spec"):
        text = (spec_dir / name).read_text(encoding="utf-8")
        if "BKPOS_version_info.txt" not in text:
            issues.append(f"{name} does not reference executable version metadata.")
    return issues
