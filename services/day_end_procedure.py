"""BKPOS Phase 70 — operator-friendly day-end and recovery procedure.

The procedure is intentionally safe: it checks the live database, creates a
verified backup, verifies that backup, and reports open shifts/cash-up issues.
It never restores or replaces the live database automatically.
"""
from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from core.deployment_config import resolve_paths
from core.logger import logger as _bkpos_logger
from .production_hardening import backup_database, prune_backups
from .recovery_hardening import full_database_health, verify_backup
from .database_maintenance import optimize_database


@dataclass(frozen=True)
class DayEndCheck:
    name: str
    status: str
    message: str
    details: dict[str, Any] | None = None


def _check(name: str, fn) -> DayEndCheck:
    try:
        status, message, details = fn()
        return DayEndCheck(name, status, message, details or {})
    except Exception as exc:
        return DayEndCheck(name, "ERROR", f"{type(exc).__name__}: {exc}", {})


def check_open_shifts(conn: sqlite3.Connection) -> tuple[str, str, dict]:
    row = conn.execute(
        "SELECT COUNT(*) FROM cashier_shifts WHERE status='OPEN'"
    ).fetchone()
    count = int(row[0] or 0)
    if count:
        rows = conn.execute(
            "SELECT id, cashier, opened_at FROM cashier_shifts "
            "WHERE status='OPEN' ORDER BY id"
        ).fetchall()
        return "WARN", f"{count} cashier shift(s) are still open.", {
            "open_shifts": [dict(id=r[0], cashier=r[1], opened_at=r[2]) for r in rows]
        }
    return "OK", "All cashier shifts are closed.", {"open_shifts": 0}


def check_cashup_variances(conn: sqlite3.Connection, tolerance: float = 0.01) -> tuple[str, str, dict]:
    try:
        rows = conn.execute(
            "SELECT id, cashup_date, cashier, difference, variance_reason "
            "FROM cashup_records WHERE ABS(COALESCE(difference,0)) > ? ORDER BY id",
            (float(tolerance),),
        ).fetchall()
    except sqlite3.DatabaseError:
        return "OK", "Cash-up variance table is not available on this database.", {"unsupported": True}
    if rows:
        return "WARN", f"{len(rows)} cash-up variance(s) exceed tolerance.", {
            "variances": [dict(id=r[0], date=r[1], cashier=r[2], difference=r[3], reason=r[4]) for r in rows]
        }
    return "OK", "No cash-up variances exceed tolerance.", {"variances": 0, "tolerance": tolerance}


def create_verified_day_end_backup(db_path: str | os.PathLike, backup_dir: str | os.PathLike | None = None) -> dict:
    db = Path(db_path)
    if not db.is_file():
        return {"ok": False, "error": "Live database file does not exist."}
    directory = Path(backup_dir) if backup_dir else resolve_paths().backup_dir
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    destination = directory / f"pos_store_day_end_{stamp}.db"
    try:
        path = backup_database(db, destination)
        health = verify_backup(path)
        if not health.get("ok"):
            destination.unlink(missing_ok=True)
            return {"ok": False, "error": "; ".join(health.get("problems", [])), "health": health}
        removed = prune_backups(directory, keep=20)
        return {"ok": True, "path": str(path), "size_bytes": destination.stat().st_size,
                "health": health, "old_backups_removed": removed}
    except (OSError, sqlite3.DatabaseError, RuntimeError, ValueError) as exc:
        return {"ok": False, "error": str(exc)}


def run_day_end(db_path: str | os.PathLike | None = None, *, optimize: bool = True) -> dict:
    """Run the operator day-end checklist and create a verified backup."""
    paths = resolve_paths()
    db = Path(db_path) if db_path else paths.database_path
    checks: list[DayEndCheck] = []
    health = full_database_health(db)
    checks.append(DayEndCheck(
        "database_health", "OK" if health.get("ok") else "ERROR",
        "Database health is clean." if health.get("ok") else "; ".join(health.get("problems", [])),
        health,
    ))
    if health.get("ok"):
        conn = sqlite3.connect(str(db))
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            if _table_exists(conn, "cashier_shifts"):
                checks.append(_check("open_shifts", lambda: check_open_shifts(conn)))
            if _table_exists(conn, "cashup_records"):
                checks.append(_check("cashup_variances", lambda: check_cashup_variances(conn)))
        finally:
            conn.close()
    if health.get("ok"):
        backup = create_verified_day_end_backup(db, paths.backup_dir)
    else:
        backup = {"ok": False, "skipped": True, "error": "Backup skipped because database health is not clean."}
    checks.append(DayEndCheck(
        "verified_backup", "OK" if backup.get("ok") else ("WARN" if backup.get("skipped") else "ERROR"),
        "Verified day-end backup created." if backup.get("ok") else backup.get("error", "Backup failed."),
        backup,
    ))
    maintenance = None
    if optimize and health.get("ok"):
        try:
            conn = sqlite3.connect(str(db))
            result = optimize_database(conn)
            maintenance = {"ok": bool(result.ok), "message": result.message, "operation": result.operation}
        except Exception as exc:
            maintenance = {"ok": False, "error": str(exc)}
        finally:
            try:
                conn.close()
            except Exception as exc:
                _bkpos_logger.debug("Database connection was already closed at day-end cleanup: %s", exc)
        checks.append(DayEndCheck(
            "database_optimization", "OK" if maintenance.get("ok") else "WARN",
            "Database planner statistics refreshed." if maintenance.get("ok") else maintenance.get("error", "Optimization unavailable."),
            maintenance,
        ))
    errors = sum(c.status == "ERROR" for c in checks)
    warnings = sum(c.status == "WARN" for c in checks)
    return {
        "ok": errors == 0,
        "overall": "ERROR" if errors else ("WARN" if warnings else "OK"),
        "database": str(db),
        "checks": [asdict(c) for c in checks],
        "backup": backup,
        "maintenance": maintenance,
        "operator_note": "Do not restore the live database during normal day-end. Use recovery validation first if recovery is required.",
    }


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None
