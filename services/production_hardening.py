"""Production hardening helpers for BKPOS.

All helpers are dependency-free and intentionally separate from Tkinter so they
can be tested and used by the desktop UI without changing business workflows.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path


def integrity_check(path: str | os.PathLike) -> bool:
    """Return True only when SQLite reports a clean integrity check."""
    try:
        db = sqlite3.connect(str(path))
        try:
            return db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            db.close()
    except (sqlite3.DatabaseError, OSError):
        return False


def backup_database(source: str | os.PathLike, destination: str | os.PathLike) -> str:
    """Create a consistent SQLite backup using SQLite's online backup API.

    This is safer than copying a live database file while writes may be in
    progress. The destination is written to a temporary file first, verified,
    then atomically renamed into place.
    """
    source = os.path.abspath(str(source))
    destination = os.path.abspath(str(destination))
    if not os.path.isfile(source):
        raise FileNotFoundError(source)
    os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".mipos_backup_", suffix=".db", dir=os.path.dirname(destination) or ".")
    os.close(fd)
    try:
        src = sqlite3.connect(source)
        dst = sqlite3.connect(tmp)
        try:
            src.backup(dst)
            dst.commit()
        finally:
            dst.close()
            src.close()
        if not integrity_check(tmp):
            raise RuntimeError("Backup verification failed.")
        os.replace(tmp, destination)
        return destination
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def restore_database(source_backup: str | os.PathLike, destination: str | os.PathLike, safety_backup: str | os.PathLike | None = None) -> str | None:
    """Restore a verified backup, creating a verified safety backup first."""
    source_backup = os.path.abspath(str(source_backup))
    destination = os.path.abspath(str(destination))
    if not integrity_check(source_backup):
        raise ValueError("Selected backup failed SQLite integrity verification.")
    created_safety = None
    if os.path.exists(destination):
        if safety_backup is None:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safety_backup = os.path.join(os.path.dirname(destination), f"pos_store_before_restore_{stamp}.db")
        created_safety = backup_database(destination, safety_backup)
    # Restore through the same online backup mechanism and atomic replacement.
    restored_tmp = destination + ".restore_tmp"
    try:
        backup_database(source_backup, restored_tmp)
        os.replace(restored_tmp, destination)
        if not integrity_check(destination):
            raise RuntimeError("Restored database failed integrity verification.")
    finally:
        if os.path.exists(restored_tmp):
            os.remove(restored_tmp)
    return created_safety


def prune_backups(directory: str | os.PathLike, keep: int = 20) -> int:
    """Delete old .db backups, keeping the newest *keep* files."""
    if keep < 1:
        raise ValueError("keep must be at least 1")
    directory = Path(directory)
    if not directory.exists():
        return 0
    files = sorted(directory.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    removed = 0
    for path in files[keep:]:
        path.unlink()
        removed += 1
    return removed


def require_permission(permissions: dict, permission: str) -> None:
    """Raise PermissionError when a business operation is not authorized."""
    if not permissions or not bool(permissions.get(permission, False)):
        raise PermissionError(f"Permission denied: {permission}")
