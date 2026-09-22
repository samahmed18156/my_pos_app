"""BKPOS Phase 64 — configuration and deployment policy.

Keeps deployment paths and release identity in one small, testable module.
Source-mode data remains with the PyCharm project; packaged Windows builds
store the executable under LocalAppData and writable data under AppData.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "BKPOS"
APP_VERSION = "10.0.0"


@dataclass(frozen=True)
class DeploymentPaths:
    """Resolved paths used by BKPOS at runtime."""
    app_base_dir: Path
    data_dir: Path
    database_path: Path
    backup_dir: Path
    receipt_dir: Path
    generated_report_dir: Path
    log_dir: Path
    diagnostics_dir: Path
    runtime_dir: Path


def is_packaged() -> bool:
    return bool(getattr(sys, "frozen", False))


def _user_data_root() -> Path:
    """Return the writable per-user data root used by packaged BKPOS."""
    root = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
    if root:
        return Path(root) / APP_NAME
    # Defensive fallback for unusual Windows environments.
    return Path.home() / "AppData" / "Roaming" / APP_NAME


def resolve_paths() -> DeploymentPaths:
    """Resolve all BKPOS paths without creating files or directories."""
    if is_packaged():
        app_base = Path(sys.executable).resolve().parent
        data = _user_data_root()
    else:
        app_base = Path(__file__).resolve().parents[1]
        data = app_base

    return DeploymentPaths(
        app_base_dir=app_base,
        data_dir=data,
        database_path=data / "pos_store.db",
        backup_dir=data / "backups",
        receipt_dir=data / "receipts",
        generated_report_dir=data / "generated",
        log_dir=data / "logs",
        diagnostics_dir=data / "diagnostics",
        runtime_dir=data / "runtime",
    )


def deployment_summary() -> dict:
    """Return safe, non-secret deployment information for diagnostics."""
    paths = resolve_paths()
    return {
        "app_name": APP_NAME,
        "app_version": APP_VERSION,
        "packaged": is_packaged(),
        "app_base_dir": str(paths.app_base_dir),
        "data_dir": str(paths.data_dir),
        "database_path": str(paths.database_path),
        "backup_dir": str(paths.backup_dir),
        "receipt_dir": str(paths.receipt_dir),
        "generated_report_dir": str(paths.generated_report_dir),
        "log_dir": str(paths.log_dir),
        "diagnostics_dir": str(paths.diagnostics_dir),
        "runtime_dir": str(paths.runtime_dir),
    }


def validate_deployment_paths(paths: DeploymentPaths | None = None) -> list[str]:
    """Validate path policy without creating or modifying anything."""
    paths = paths or resolve_paths()
    issues: list[str] = []

    if not paths.app_base_dir:
        issues.append("Application base directory is empty.")
    if paths.database_path.parent != paths.data_dir:
        issues.append("Database path is not inside the BKPOS data directory.")
    if paths.backup_dir == paths.app_base_dir:
        issues.append("Backup directory must not be the application directory.")

    if is_packaged() and paths.data_dir == paths.app_base_dir:
        issues.append("Packaged BKPOS data must be separate from the application directory.")

    return issues
