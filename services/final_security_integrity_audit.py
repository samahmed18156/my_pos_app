"""BKPOS Phase 79 — final security and data-integrity audit gate.

Read-only release checks plus isolated SQLite invariant checks.  The gate never
opens or modifies the live BKPOS database; runtime checks use in-memory SQLite.
"""
from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

from core.permissions import has_permission, require_permission
from core.release_identity import validate_release_identity
from core.schema_manager import SCHEMA_VERSION
from services.transaction_integrity import assert_sale_integrity

SENSITIVE_PERMISSIONS = (
    "backup_restore", "user_management", "stock_adjustment", "price_change",
    "creditor_payment", "system_settings", "audit_history",
)
REQUIRED_SECURITY_FILES = (
    "core/permissions.py",
    "core/audit_log.py",
    "core/schema_manager.py",
    "services/transaction_integrity.py",
    "services/final_production_audit.py",
    "services/release_gate.py",
    "services/upgrade_safety.py",
)


def validate_security_integrity_gate(root: str | Path) -> list[str]:
    root = Path(root)
    issues: list[str] = []

    for rel in REQUIRED_SECURITY_FILES:
        if not (root / rel).is_file():
            issues.append(f"Missing security/integrity file: {rel}")

    # Canonical role boundary: cashier must not gain administrative controls.
    for permission in SENSITIVE_PERMISSIONS:
        if has_permission("cashier", permission):
            issues.append(f"Cashier is incorrectly allowed: {permission}")
    for role, permission in (("admin", "user_management"), ("manager", "grn"), ("cashier", "sales")):
        try:
            require_permission(role, permission)
        except PermissionError:
            issues.append(f"Expected permission denied unexpectedly: {role}/{permission}")

    # Newer DB schemas must not be accepted by an older release.
    if SCHEMA_VERSION < 4:
        issues.append("Schema version is below the production transaction-integrity baseline.")

    # Audit protection must remain append-only in the canonical legacy table.
    audit_path = root / "audit_log.py"
    if audit_path.is_file():
        text = audit_path.read_text(encoding="utf-8", errors="replace")
        for marker in ("trg_audit_log_no_update", "trg_audit_log_no_delete", "append-only"):
            if marker not in text:
                issues.append(f"Audit protection marker missing: {marker}")

    # Parse security-critical modules independently of the broader source audit.
    for rel in REQUIRED_SECURITY_FILES:
        path = root / rel
        if path.is_file():
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (SyntaxError, UnicodeDecodeError) as exc:
                issues.append(f"Security module syntax error: {rel}: {exc}")

    # Release identity remains a required boundary.
    try:
        issues.extend(validate_release_identity())
    except (OSError, UnicodeDecodeError) as exc:
        issues.append(f"Release identity validation failed: {exc}")

    # Isolated integrity proof: a sale header must reconcile to its line totals/COGS.
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript("""
            CREATE TABLE sales_history (id INTEGER PRIMARY KEY, total_amount REAL, total_cost REAL);
            CREATE TABLE sale_items (id INTEGER PRIMARY KEY, sale_id INTEGER, value REAL, qty REAL, cost_price REAL);
            INSERT INTO sales_history VALUES (1, 120.00, 70.00);
            INSERT INTO sale_items VALUES (1, 1, 50.00, 1, 30.00);
            INSERT INTO sale_items VALUES (2, 1, 70.00, 2, 20.00);
        """)
        try:
            assert_sale_integrity(conn, 1)
        except AssertionError as exc:
            issues.append(f"Isolated sale integrity check failed: {exc}")
    finally:
        conn.close()

    return sorted(set(issues))


def security_integrity_summary(root: str | Path) -> dict[str, object]:
    issues = validate_security_integrity_gate(root)
    return {
        "schema_version": SCHEMA_VERSION,
        "ok": not issues,
        "issues": issues,
        "live_database_touched": False,
    }
