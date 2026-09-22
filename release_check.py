"""Headless Release Candidate checks for BKPOS.

This script deliberately avoids Tkinter windows and physical hardware. It checks
that a clean first-run database can be created, the active modules import, the
database is structurally sound, and the automated suite passes.
"""
from __future__ import annotations
import importlib
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

CORE_MODULES = [
    "database", "login", "security", "permissions", "services.sales_service",
    "services.returns_service", "services.grn_service", "services.stock_service",
    "services.branch_stock_service", "services.accounts_service",
    "services.supplier_credit_service", "services.financial_reconciliation",
    "services.production_hardening", "disaster_recovery", "health_check",
    "phase37_business_controls",
]


def check_imports():
    for name in CORE_MODULES:
        importlib.import_module(name)
    return True


def check_clean_first_launch():
    import database
    old = database.DB_PATH
    try:
        with tempfile.TemporaryDirectory() as td:
            database.DB_PATH = os.path.join(td, "pos_store.db")
            database.init_db()
            con = sqlite3.connect(database.DB_PATH)
            try:
                assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                required = {"products", "users", "sales_history", "sale_items", "stock_movements", "branches"}
                assert required <= tables, f"missing tables: {sorted(required - tables)}"
                assert con.execute("SELECT COUNT(*) FROM users").fetchone()[0] >= 1
            finally:
                con.close()
    finally:
        database.DB_PATH = old
    return True


def check_database_safety_helpers():
    import core.config as config
    assert os.path.basename(config.DB_PATH) == "pos_store.db"
    assert os.path.basename(config.BACKUP_DIR) == "backups"
    return True


def check_phase37_controls():
    import phase37_business_controls
    phase37_business_controls.run()
    return True


def main():
    check_imports(); print("IMPORT CHECK: PASS")
    check_database_safety_helpers(); print("DATABASE SAFETY CONFIG: PASS")
    check_phase37_controls(); print("PHASE 37 BUSINESS CONTROLS: PASS")
    check_clean_first_launch(); print("FIRST-LAUNCH DATABASE CHECK: PASS")
    tests = subprocess.run([sys.executable, str(BASE_DIR / "run_tests.py")], cwd=BASE_DIR)
    if tests.returncode:
        print("AUTOMATED TEST SUITE: FAIL")
        return tests.returncode
    print("AUTOMATED TEST SUITE: PASS")
    print("RELEASE CANDIDATE CHECK: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
