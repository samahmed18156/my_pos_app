"""BKPOS Phase 56 — runtime environment diagnostics.

Read-only diagnostics for the folders and optional external components BKPOS
uses at runtime. The module does not create files, alter configuration, or
change the database.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from dataclasses import asdict, dataclass
from typing import Any

from core import config


@dataclass(frozen=True)
class RuntimeCheck:
    name: str
    status: str
    message: str
    details: dict[str, Any]


def _check_dir(name: str, path: str | os.PathLike[str]) -> RuntimeCheck:
    p = Path(path)
    if not p.exists():
        return RuntimeCheck(name, "WARN", "Directory does not exist.", {"path": str(p)})
    if not p.is_dir():
        return RuntimeCheck(name, "ERROR", "Path is not a directory.", {"path": str(p)})
    readable = os.access(p, os.R_OK)
    writable = os.access(p, os.W_OK)
    if not readable:
        return RuntimeCheck(name, "ERROR", "Directory is not readable.", {"path": str(p)})
    if not writable:
        return RuntimeCheck(name, "ERROR", "Directory is not writable.", {"path": str(p)})
    return RuntimeCheck(name, "OK", "Directory is readable and writable.", {"path": str(p)})


def check_runtime_directories() -> list[RuntimeCheck]:
    """Check writable runtime locations without creating probe files."""
    return [
        _check_dir("data_directory", config.DATA_DIR),
        _check_dir("backup_directory", config.BACKUP_DIR),
        _check_dir("receipt_directory", config.RECEIPT_DIR),
        _check_dir("report_directory", config.GENERATED_REPORT_DIR),
    ]


def check_database_file() -> RuntimeCheck:
    p = Path(config.DB_PATH)
    if not p.exists():
        return RuntimeCheck("database_file", "WARN", "Database file does not exist yet.", {"path": str(p)})
    if not p.is_file():
        return RuntimeCheck("database_file", "ERROR", "Database path is not a file.", {"path": str(p)})
    if not os.access(p, os.R_OK):
        return RuntimeCheck("database_file", "ERROR", "Database file is not readable.", {"path": str(p)})
    if not os.access(p, os.W_OK):
        return RuntimeCheck("database_file", "ERROR", "Database file is not writable.", {"path": str(p)})
    return RuntimeCheck("database_file", "OK", "Database file is readable and writable.", {"path": str(p), "size_bytes": p.stat().st_size})


def check_disk_space(path: str | os.PathLike[str] | None = None, minimum_free_mb: int = 100) -> RuntimeCheck:
    """Warn when the target filesystem has less than the requested free space."""
    target = Path(path or config.DATA_DIR)
    try:
        usage = shutil.disk_usage(target)
    except OSError as exc:
        return RuntimeCheck("disk_space", "ERROR", f"Unable to inspect disk space: {exc}", {"path": str(target)})
    free_mb = usage.free / (1024 * 1024)
    status = "OK" if free_mb >= minimum_free_mb else "WARN"
    message = "Sufficient free disk space." if status == "OK" else "Low free disk space."
    return RuntimeCheck(
        "disk_space", status, message,
        {"path": str(target), "free_bytes": usage.free, "free_mb": round(free_mb, 1), "minimum_free_mb": minimum_free_mb},
    )


def check_java() -> RuntimeCheck:
    """Report Java availability; Java is optional for normal non-Jasper use."""
    java = shutil.which("java")
    if java:
        return RuntimeCheck("java", "OK", "Java executable is available on PATH.", {"executable": java})
    return RuntimeCheck("java", "WARN", "Java executable was not found on PATH; JasperViewer may be unavailable.", {})


def run_runtime_diagnostics(minimum_free_mb: int = 100) -> dict[str, Any]:
    """Run non-invasive deployment/runtime diagnostics."""
    checks = check_runtime_directories() + [
        check_database_file(),
        check_disk_space(minimum_free_mb=minimum_free_mb),
        check_java(),
    ]
    errors = sum(c.status == "ERROR" for c in checks)
    warnings = sum(c.status == "WARN" for c in checks)
    return {
        "phase": 56,
        "overall": "ERROR" if errors else ("WARN" if warnings else "OK"),
        "checks": [asdict(c) for c in checks],
        "packaged": bool(getattr(sys, "frozen", False)),
        "app_version": config.APP_VERSION,
        "read_only": True,
    }
