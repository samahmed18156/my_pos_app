"""Final release hardening utilities for BKPOS.

These helpers keep operational checks outside the Tkinter UI and are safe to
run before opening the application.
"""
from __future__ import annotations
import os
import sqlite3
from pathlib import Path
from .production_hardening import backup_database, integrity_check, prune_backups

REQUIRED_TABLES = {
    "users", "products", "branches", "stock_movements",
    "sales", "sale_items", "customers", "account_transactions",
}

def preflight_database(db_path: str | os.PathLike) -> dict:
    """Validate that a BKPOS database is readable, intact, and has core tables."""
    path = Path(db_path)
    result = {"path": str(path), "exists": path.is_file(), "integrity": False,
              "missing_tables": [], "ok": False}
    if not result["exists"]:
        return result
    result["integrity"] = integrity_check(path)
    if not result["integrity"]:
        return result
    con = sqlite3.connect(str(path))
    try:
        found = {r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        con.close()
    result["missing_tables"] = sorted(REQUIRED_TABLES - found)
    result["ok"] = not result["missing_tables"]
    return result

def create_release_backup(db_path: str | os.PathLike, backup_dir: str | os.PathLike,
                          keep: int = 30) -> str:
    """Create a verified timestamped backup and prune old backups."""
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = __import__("datetime").datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    destination = backup_dir / f"pos_store_{stamp}.db"
    path = backup_database(db_path, destination)
    prune_backups(backup_dir, keep=keep)
    return path
