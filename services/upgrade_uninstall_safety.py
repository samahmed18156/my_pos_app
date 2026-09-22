"""BKPOS Phase 76 — installer upgrade/uninstall data protection.

Read-only policy checks proving that Windows installation and uninstall scripts
operate on the application directory only and do not delete BKPOS user data.
"""
from __future__ import annotations

from pathlib import Path

from core.release_identity import APP_NAME, APP_VERSION, INSTALLER_APP_ID

INSTALLERS = (
    "packaging/windows/BKPOS.iss",
    "packaging/windows/BKPOS_Windows10.iss",
)

FORBIDDEN_UNINSTALL_TOKENS = (
    "{appdata}\\BKPOS",
    "{appdata}/BKPOS",
    "pos_store.db",
)


def validate_installer_data_protection(root: Path) -> list[str]:
    """Return installer upgrade/uninstall safety issues without changing files."""
    root = Path(root)
    issues: list[str] = []
    for rel in INSTALLERS:
        path = root / rel
        if not path.is_file():
            issues.append(f"Missing installer script: {rel}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if f"#define MyAppVersion \"{APP_VERSION}\"" not in text:
            issues.append(f"Installer version mismatch: {rel}")
        if INSTALLER_APP_ID not in text:
            issues.append(f"Installer AppId mismatch: {rel}")
        if "DefaultDirName={localappdata}\\BKPOS" not in text:
            issues.append(f"Installer application directory mismatch: {rel}")
        if "PrivilegesRequired=lowest" not in text:
            issues.append(f"Installer is not per-user: {rel}")
        # BKPOS data is under the user's AppData tree and must survive an app update
        # or uninstall. No [UninstallDelete] entry or live DB reference is permitted.
        if "[UninstallDelete]" in text:
            issues.append(f"Installer must not define [UninstallDelete] for BKPOS: {rel}")
        # User-data references are allowed only for the harmless Start Menu
        # Data Folder shortcut. They must not occur in file sources/destinations.
        for token in FORBIDDEN_UNINSTALL_TOKENS:
            if token.lower() in text.lower():
                issues.append(f"Installer must not delete/reference protected data ({token}): {rel}")
        for line in text.splitlines():
            lower = line.lower()
            if "source:" in lower and ("{userappdata}\\bkpos" in lower or "{appdata}\\bkpos" in lower):
                issues.append(f"Installer must not package user data: {rel}")
            if "[uninstalldelete]" in lower:
                break
        if "{userappdata}\\BKPOS" not in text:
            # The Data Folder shortcut is intentionally expected in the installer.
            # This keeps the check explicit and protects against accidental removal
            # of the operator's data location from the Start Menu.
            issues.append(f"Installer missing BKPOS Data Folder shortcut: {rel}")
    return sorted(set(issues))


def upgrade_uninstall_safety_summary(root: Path) -> dict[str, object]:
    issues = validate_installer_data_protection(root)
    return {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "safe": not issues,
        "issues": issues,
    }
