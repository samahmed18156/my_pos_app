"""Central BKPOS runtime configuration.

Phase 64 keeps deployment identity and path policy in ``core.deployment_config``.
Source mode keeps the project-local database for development compatibility.
Packaged Windows builds keep the installed application separate from writable
per-user data so BKPOS does not require Administrator rights.
"""
from core.logger import logger as _bkpos_logger
import os
import sys
import shutil
import sqlite3
from datetime import datetime

from core.deployment_config import (
    APP_NAME,
    APP_VERSION,
    is_packaged,
    resolve_paths,
)

_paths = resolve_paths()
APP_BASE_DIR = str(_paths.app_base_dir)
DATA_DIR = str(_paths.data_dir)
DB_PATH = str(_paths.database_path)
BACKUP_DIR = str(_paths.backup_dir)
RECEIPT_DIR = str(_paths.receipt_dir)
GENERATED_REPORT_DIR = str(_paths.generated_report_dir)

os.makedirs(DATA_DIR, exist_ok=True)


def _startup_database_safety():
    """Create one verified daily backup of an existing packaged database.

    This is deliberately best-effort: a backup failure never prevents a user
    from opening BKPOS. Existing data is never deleted or replaced here.
    """
    if not is_packaged() or not os.path.isfile(DB_PATH):
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    day = datetime.now().strftime("%Y%m%d")
    target = os.path.join(BACKUP_DIR, f"pos_store_daily_{day}.db")
    if os.path.isfile(target):
        return target

    source = sqlite3.connect(DB_PATH)
    try:
        check = source.execute("PRAGMA integrity_check").fetchone()
        if not check or check[0] != "ok":
            raise RuntimeError(f"Database integrity check failed: {check}")
        tmp = target + ".tmp"
        destination = sqlite3.connect(tmp)
        try:
            source.backup(destination)
            destination.commit()
            copied = destination.execute("PRAGMA integrity_check").fetchone()
            if not copied or copied[0] != "ok":
                raise RuntimeError(f"Backup integrity check failed: {copied}")
        finally:
            destination.close()
        os.replace(tmp, target)
        return target
    except Exception as exc:
        try:
            if os.path.exists(target + ".tmp"):
                os.remove(target + ".tmp")
        except OSError:
            _bkpos_logger.warning("Suppressed exception in core/config.py", exc_info=exc)
        return None
    finally:
        source.close()


def _migrate_legacy_mipos_database():
    """Safely migrate a legacy packaged MiPOS database to BKPOS."""
    if not is_packaged():
        return

    appdata_root = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
    if not appdata_root:
        return

    legacy_dir = os.path.join(appdata_root, "MiPOS")
    legacy_db = os.path.join(legacy_dir, "pos_store.db")

    if os.path.exists(DB_PATH) or not os.path.isfile(legacy_db):
        return

    os.makedirs(BACKUP_DIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(BACKUP_DIR, f"mipos_pre_bkpos_migration_{stamp}.db")
    temp_path = DB_PATH + ".migration.tmp"

    try:
        shutil.copy2(legacy_db, backup_path)
        source = sqlite3.connect(legacy_db)
        try:
            destination = sqlite3.connect(temp_path)
            try:
                source.backup(destination)
                destination.commit()
                check = destination.execute("PRAGMA integrity_check").fetchone()
                if not check or check[0] != "ok":
                    raise RuntimeError(f"Migrated database integrity check failed: {check}")
            finally:
                destination.close()
        finally:
            source.close()

        os.replace(temp_path, DB_PATH)
    except Exception as exc:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                _bkpos_logger.warning("Suppressed exception in core/config.py", exc_info=exc)
        raise RuntimeError(
            "BKPOS could not safely migrate the existing MiPOS database. "
            f"The original database was left untouched. Safety backup: {backup_path}"
        )


_migrate_legacy_mipos_database()
