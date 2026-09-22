"""BKPOS Phase 57 — production deployment preflight.

Combines the existing read-only runtime and database diagnostics into one
operator-friendly preflight report. It never creates, repairs, migrates, or
modifies application data.
"""
from __future__ import annotations

import sqlite3
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from core import config
from .recovery_hardening import full_database_health
from .runtime_diagnostics import run_runtime_diagnostics


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    status: str
    message: str
    details: dict[str, Any]


def check_schema_version(db_path: str | Path) -> PreflightCheck:
    """Report SQLite application schema version without changing it."""
    p = Path(db_path)
    if not p.is_file():
        return PreflightCheck("schema_version", "WARN", "Database file is not present yet.", {"path": str(p)})
    try:
        with sqlite3.connect(str(p)) as conn:
            version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        return PreflightCheck("schema_version", "OK", f"Database schema version is {version}.", {"version": version})
    except (sqlite3.DatabaseError, OSError) as exc:
        return PreflightCheck("schema_version", "ERROR", f"Unable to read schema version: {exc}", {"error": str(exc)})


def check_database_health(db_path: str | Path) -> PreflightCheck:
    """Run the established non-mutating BKPOS database health validation."""
    result = full_database_health(db_path)
    if result.get("ok"):
        return PreflightCheck("database_health", "OK", "Database passed BKPOS health validation.", result)
    problems = result.get("problems") or ["Database health validation failed."]
    return PreflightCheck("database_health", "ERROR", "; ".join(problems), result)


def run_deployment_preflight(db_path: str | Path | None = None, minimum_free_mb: int = 100) -> dict[str, Any]:
    """Return a single read-only go/no-go report for a BKPOS installation."""
    target = Path(db_path or config.DB_PATH)
    runtime = run_runtime_diagnostics(minimum_free_mb=minimum_free_mb)
    checks = [
        PreflightCheck("runtime", runtime["overall"], f"Runtime diagnostics: {runtime['overall']}.", runtime),
        check_schema_version(target),
    ]
    if target.is_file():
        checks.append(check_database_health(target))
    else:
        checks.append(PreflightCheck("database_health", "WARN", "Database has not been created yet; first launch will initialize it.", {"path": str(target)}))

    errors = sum(c.status == "ERROR" for c in checks)
    warnings = sum(c.status == "WARN" for c in checks)
    overall = "ERROR" if errors else ("WARN" if warnings else "OK")
    return {
        "phase": 57,
        "overall": overall,
        "ready": errors == 0,
        "checks": [asdict(c) for c in checks],
        "db_path": str(target),
        "python": sys.version.split()[0],
        "app_version": config.APP_VERSION,
        "packaged": bool(getattr(sys, "frozen", False)),
        "read_only": True,
    }
