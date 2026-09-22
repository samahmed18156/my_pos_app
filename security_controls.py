"""Central authorization and audit controls for BKPOS.

This module is deliberately independent of Tkinter.  UI code can call the same
checks as services, preventing a hidden/disabled button from being the only
security boundary.
"""
from __future__ import annotations
import sqlite3
from core.config import DB_PATH
from audit_log import log_action

DB_NAME = DB_PATH

PERMISSIONS = (
    "can_edit_price", "can_edit_qty", "can_delete_items", "can_view_reports",
    "can_access_stock", "can_access_debtors", "can_access_creditors", "can_access_utility",
    "can_void_sales", "can_issue_credit_notes", "can_manage_users", "can_manage_branches",
    "can_cashup", "can_manage_expenses",
)


def ensure_permission_schema(conn=None):
    own = conn is None
    c = conn or sqlite3.connect(DB_NAME)
    try:
        cols = {r[1] for r in c.execute("PRAGMA table_info(users)").fetchall()}
        for p in PERMISSIONS:
            if p not in cols:
                c.execute(f"ALTER TABLE users ADD COLUMN {p} INTEGER NOT NULL DEFAULT 0")
        if own:
            c.commit()
    finally:
        if own:
            c.close()


def is_admin(actor: dict | None) -> bool:
    return str((actor or {}).get("role", "")).strip().lower() == "admin" or bool((actor or {}).get("is_admin"))


def has_permission(actor: dict | None, permission: str) -> bool:
    if is_admin(actor):
        return True
    return bool((actor or {}).get(permission, False))


def require_permission(actor: dict | None, permission: str) -> None:
    if not has_permission(actor, permission):
        raise PermissionError(f"Permission denied: {permission}")


def require_branch(actor: dict | None, branch_id: int) -> int:
    """Enforce branch isolation for non-admin users."""
    bid = int(branch_id or 1)
    if is_admin(actor):
        return bid
    actor_bid = actor.get("branch_id") if actor else None
    if actor_bid is None:
        raise PermissionError("User is not assigned to a branch.")
    if int(actor_bid) != bid:
        raise PermissionError("You are not authorized to operate on another branch.")
    return bid


def audit_security(actor: dict | None, action: str, entity_type: str = "", entity_id: str = "", details: str = "", branch_id: int | None = None):
    actor = actor or {}
    log_action(actor.get("username", "Unknown"), action, entity_type, entity_id,
               details, actor.get("role", ""), branch_id or actor.get("branch_id") or 1)
