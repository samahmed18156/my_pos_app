"""BKPOS Phase 62 backup/restore validation helpers.

Safe, non-destructive validation routines for production support and release
checks. Validation uses temporary files and never replaces the live database.
"""
from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Any

from .production_hardening import backup_database
from .recovery_hardening import full_database_health, restore_to_new_file


def validate_backup_roundtrip(source: str | os.PathLike) -> dict[str, Any]:
    """Backup a database to a temporary file, validate it, and compare basics."""
    src = Path(source)
    if not src.is_file():
        return {"ok": False, "stage": "source", "error": "Database file does not exist."}

    before = full_database_health(src)
    if not before["ok"]:
        return {"ok": False, "stage": "source", "error": "; ".join(before["problems"]), "source": before}

    fd, name = tempfile.mkstemp(prefix="bkpos_phase62_", suffix=".db")
    os.close(fd)
    temp = Path(name)
    try:
        backup_database(src, temp)
        after = full_database_health(temp)
        if not after["ok"]:
            return {"ok": False, "stage": "backup", "error": "; ".join(after["problems"]), "source": before, "backup": after}
        source_size = src.stat().st_size
        backup_size = temp.stat().st_size
        return {
            "ok": True,
            "stage": "complete",
            "source": before,
            "backup": after,
            "source_size": source_size,
            "backup_size": backup_size,
            "size_match": source_size == backup_size,
        }
    except (OSError, sqlite3.DatabaseError, RuntimeError, ValueError) as exc:
        return {"ok": False, "stage": "backup", "error": str(exc), "source": before}
    finally:
        temp.unlink(missing_ok=True)


def validate_restore_roundtrip(source_backup: str | os.PathLike) -> dict[str, Any]:
    """Restore a verified backup into a temporary destination and validate it."""
    backup = Path(source_backup)
    if not backup.is_file():
        return {"ok": False, "stage": "source", "error": "Backup file does not exist."}
    pre = full_database_health(backup)
    if not pre["ok"]:
        return {"ok": False, "stage": "source", "error": "; ".join(pre["problems"]), "backup": pre}
    with tempfile.TemporaryDirectory(prefix="bkpos_phase62_restore_") as td:
        dest = Path(td) / "restored.db"
        try:
            post = restore_to_new_file(backup, dest)
            return {"ok": bool(post["ok"]), "stage": "complete", "backup": pre, "restored": post}
        except (OSError, sqlite3.DatabaseError, RuntimeError, ValueError) as exc:
            return {"ok": False, "stage": "restore", "error": str(exc), "backup": pre}
