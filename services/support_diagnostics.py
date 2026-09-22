"""BKPOS Phase 60 — safe production support diagnostics.

Builds a small, human-readable diagnostic report without copying the live
SQLite database or exposing credentials/secrets. The report is intended for
troubleshooting packaged installations.
"""
from __future__ import annotations

import os
import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from core.config import APP_VERSION, DB_PATH, DATA_DIR
from services.logging_hardening import logging_status
from services.production_health import run_health_check
from services.runtime_diagnostics import run_runtime_diagnostics
from services.lifecycle_hardening import lifecycle_status


def _safe_value(value: Any) -> str:
    text = str(value)
    for secret in ("password", "passwd", "secret", "token", "api_key", "apikey"):
        if secret in text.lower():
            return "***REDACTED***"
    return text


def collect_support_diagnostics() -> dict[str, Any]:
    """Collect non-sensitive runtime facts useful for support."""
    runtime = run_runtime_diagnostics()
    health = run_health_check(DB_PATH)
    logging = logging_status()
    lifecycle = lifecycle_status()
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "app_version": APP_VERSION,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "frozen": bool(getattr(sys, "frozen", False)),
        "data_dir": str(DATA_DIR),
        "database_path": str(DB_PATH),
        "database_exists": os.path.isfile(DB_PATH),
        "runtime_checks": runtime,
        "database_health": health,
        "logging": logging,
        "lifecycle": lifecycle,
    }


def format_support_report(data: dict[str, Any]) -> str:
    """Format diagnostics as a stable text report."""
    lines = [
        "BKPOS SUPPORT DIAGNOSTIC REPORT",
        "=" * 34,
        f"Generated: {_safe_value(data.get('generated_at', ''))}",
        f"App version: {_safe_value(data.get('app_version', ''))}",
        f"Python: {_safe_value(data.get('python_version', ''))}",
        f"Platform: {_safe_value(data.get('platform', ''))}",
        f"Machine: {_safe_value(data.get('machine', ''))}",
        f"Packaged build: {_safe_value(data.get('frozen', False))}",
        f"Database exists: {_safe_value(data.get('database_exists', False))}",
        "",
        "LOGGING",
        "-------",
    ]
    log = data.get("logging", {})
    for key in ("file_logging", "writable", "handler_count", "path"):
        lines.append(f"{key}: {_safe_value(log.get(key, ''))}")

    lines += ["", "LIFECYCLE", "---------"]
    lifecycle = data.get("lifecycle", {})
    if isinstance(lifecycle, dict):
        for key in ("status", "started_at", "shutdown_at", "previous_clean", "pid", "path"):
            lines.append(f"{key}: {_safe_value(lifecycle.get(key, ""))}")

    lines += ["", "RUNTIME CHECKS", "--------------"]
    runtime = data.get("runtime_checks")
    if isinstance(runtime, dict):
        for key, value in runtime.items():
            lines.append(f"{key}: {_safe_value(value)}")
    elif isinstance(runtime, (list, tuple)):
        for item in runtime:
            lines.append(f"- {_safe_value(item)}")
    else:
        lines.append(_safe_value(runtime))

    lines += ["", "DATABASE HEALTH", "---------------"]
    health = data.get("database_health")
    if isinstance(health, dict):
        for key, value in health.items():
            lines.append(f"{key}: {_safe_value(value)}")
    else:
        lines.append(_safe_value(health))

    return "\n".join(lines) + "\n"


def write_support_report(directory: str | os.PathLike[str] | None = None) -> Path:
    """Write diagnostics outside the application directory and return its path."""
    target_dir = Path(directory) if directory else Path(DATA_DIR) / "diagnostics"
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = target_dir / f"bkpos_support_{stamp}.txt"
    target.write_text(format_support_report(collect_support_diagnostics()), encoding="utf-8")
    return target
