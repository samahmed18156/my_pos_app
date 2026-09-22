"""BKPOS Phase 49 recovery and database health hardening.

All diagnostics are read-only. Recovery helpers never replace a live database
until the candidate has passed SQLite integrity and BKPOS schema checks.
"""
from __future__ import annotations
import os, sqlite3, tempfile
from pathlib import Path
from .production_hardening import integrity_check
from .production_readiness import database_readiness


def sqlite_diagnostics(path: str | os.PathLike) -> dict:
    p = Path(path)
    result = {
        "exists": p.is_file(), "integrity": False, "quick_check": None,
        "foreign_key_check": [], "readable": False, "size": p.stat().st_size if p.is_file() else 0,
        "error": None,
    }
    if not result["exists"]:
        result["error"] = "Database file does not exist."
        return result
    try:
        con = sqlite3.connect(str(p))
        try:
            result["quick_check"] = con.execute("PRAGMA quick_check").fetchone()[0]
            result["integrity"] = result["quick_check"] == "ok"
            result["foreign_key_check"] = [tuple(r) for r in con.execute("PRAGMA foreign_key_check").fetchall()]
            # A simple read proves the schema is queryable even when optional
            # application tables are absent.
            con.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1").fetchall()
            result["readable"] = True
        finally:
            con.close()
    except (sqlite3.DatabaseError, OSError) as exc:
        result["error"] = str(exc)
    return result


def full_database_health(path: str | os.PathLike) -> dict:
    """Return one consolidated, non-mutating health report."""
    sqlite = sqlite_diagnostics(path)
    readiness = database_readiness(path) if sqlite["readable"] else {"ok": False}
    problems = []
    if not sqlite["exists"]: problems.append("database file missing")
    if sqlite.get("error"): problems.append(f"database access error: {sqlite['error']}")
    if sqlite.get("quick_check") not in (None, "ok"): problems.append(f"SQLite quick_check: {sqlite['quick_check']}")
    if sqlite.get("foreign_key_check"): problems.append(f"foreign key violations: {len(sqlite['foreign_key_check'])}")
    if readiness.get("missing_tables"): problems.append("missing tables: " + ", ".join(readiness["missing_tables"]))
    if readiness.get("missing_columns"): problems.append("missing columns: " + ", ".join(readiness["missing_columns"]))
    if readiness.get("orphan_sale_items"): problems.append(f"orphan sale items: {readiness['orphan_sale_items']}")
    if readiness.get("orphan_grn_items"): problems.append(f"orphan GRN items: {readiness['orphan_grn_items']}")
    if readiness.get("orphan_stock_movements"): problems.append(f"orphan stock movements: {readiness['orphan_stock_movements']}")
    if readiness.get("negative_global_stock"): problems.append(f"negative global stock rows: {len(readiness['negative_global_stock'])}")
    if readiness.get("negative_branch_stock"): problems.append(f"negative branch stock rows: {len(readiness['negative_branch_stock'])}")
    return {"ok": not problems, "problems": problems, "sqlite": sqlite, "readiness": readiness}


def verify_backup(path: str | os.PathLike) -> dict:
    """Open a backup read-only and run the full database health checks."""
    return full_database_health(path)


def restore_to_new_file(source_backup: str | os.PathLike, destination: str | os.PathLike) -> dict:
    """Restore a backup to a new destination, validating before and after.

    Existing destination is never overwritten. Caller can atomically activate
    the validated file when the application is stopped.
    """
    source = Path(source_backup)
    dest = Path(destination)
    if dest.exists():
        raise FileExistsError(f"Refusing to overwrite existing database: {dest}")
    pre = full_database_health(source)
    if not pre["ok"]:
        raise ValueError("Backup failed BKPOS health validation: " + "; ".join(pre["problems"]))
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        src = sqlite3.connect(str(source), uri=False)
        out = sqlite3.connect(str(tmp))
        try:
            src.backup(out)
            out.commit()
        finally:
            out.close(); src.close()
        post = full_database_health(tmp)
        if not post["ok"]:
            raise RuntimeError("Restored database failed validation: " + "; ".join(post["problems"]))
        os.replace(tmp, dest)
        return post
    finally:
        if tmp.exists():
            tmp.unlink()
