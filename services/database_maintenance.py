"""BKPOS Phase 55 — safe SQLite maintenance helpers.

Maintenance is explicit and operationally safe: statistics/optimizer refreshes
can be run without changing business data, while VACUUM is refused when a
transaction is active because SQLite requires it to run outside a transaction.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MaintenanceResult:
    operation: str
    ok: bool
    detail: str
    changed: bool = False


def analyze_database(conn: sqlite3.Connection) -> MaintenanceResult:
    """Refresh SQLite query-planner statistics without changing business rows."""
    try:
        conn.execute("ANALYZE")
        conn.commit()
        return MaintenanceResult("ANALYZE", True, "Query planner statistics refreshed.", True)
    except sqlite3.DatabaseError as exc:
        return MaintenanceResult("ANALYZE", False, str(exc), False)


def optimize_database(conn: sqlite3.Connection) -> MaintenanceResult:
    """Ask SQLite to perform safe opportunistic optimizer maintenance."""
    try:
        row = conn.execute("PRAGMA optimize").fetchone()
        conn.commit()
        detail = "SQLite optimizer maintenance completed."
        if row:
            detail += f" Result: {tuple(row)!r}."
        return MaintenanceResult("PRAGMA optimize", True, detail, True)
    except sqlite3.DatabaseError as exc:
        return MaintenanceResult("PRAGMA optimize", False, str(exc), False)


def vacuum_database(conn: sqlite3.Connection) -> MaintenanceResult:
    """Rebuild the SQLite file to reclaim free pages; requires no active txn."""
    if conn.in_transaction:
        return MaintenanceResult(
            "VACUUM", False,
            "VACUUM refused because a transaction is active. Commit or roll back first.",
            False,
        )
    try:
        conn.execute("VACUUM")
        return MaintenanceResult("VACUUM", True, "Database vacuum completed.", True)
    except sqlite3.DatabaseError as exc:
        return MaintenanceResult("VACUUM", False, str(exc), False)


def maintenance_report(conn: sqlite3.Connection) -> dict[str, Any]:
    """Return read-only maintenance diagnostics for an operator or health check."""
    try:
        page_count = int(conn.execute("PRAGMA page_count").fetchone()[0])
        freelist_count = int(conn.execute("PRAGMA freelist_count").fetchone()[0])
        page_size = int(conn.execute("PRAGMA page_size").fetchone()[0])
        return {
            "ok": True,
            "page_count": page_count,
            "freelist_count": freelist_count,
            "page_size": page_size,
            "free_bytes": freelist_count * page_size,
            "file_bytes_estimate": page_count * page_size,
            "in_transaction": conn.in_transaction,
        }
    except sqlite3.DatabaseError as exc:
        return {"ok": False, "error": str(exc)}
