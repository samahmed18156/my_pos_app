"""BKPOS Phase 42 — lightweight audit logging.

Records important business/security events in a local append-only-style
SQLite table when a DB connection is supplied. The helper deliberately does
not alter existing transaction logic; callers can add events around approved
operations as screens are hardened.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

AUDIT_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_time TEXT NOT NULL,
    username TEXT,
    event_type TEXT NOT NULL,
    description TEXT,
    reference_type TEXT,
    reference_id TEXT,
    details_json TEXT
)
"""

def migrate_audit_table(conn) -> None:
    """Upgrade audit_log without committing a caller-owned transaction."""
    owns_transaction = not conn.in_transaction
    ensure_sql = """
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_time TEXT NOT NULL,
        username TEXT,
        event_type TEXT NOT NULL,
        description TEXT,
        reference_type TEXT,
        reference_id TEXT,
        details_json TEXT
    )
    """
    conn.execute(ensure_sql)
    columns = {row[1] for row in conn.execute("PRAGMA table_info(audit_log)").fetchall()}
    additions = {
        "event_time": "TEXT",
        "username": "TEXT",
        "event_type": "TEXT",
        "description": "TEXT",
        "reference_type": "TEXT",
        "reference_id": "TEXT",
        "details_json": "TEXT",
        # Legacy UI/modules still write these audit columns. Keep them as
        # compatibility fields while the canonical API uses event_* fields.
        "timestamp": "TEXT",
        "role": "TEXT",
        "action": "TEXT",
        "entity_type": "TEXT",
        "entity_id": "TEXT",
        "details": "TEXT",
        "branch_id": "INTEGER DEFAULT 1",
        "reference": "TEXT",
    }
    for column, sql_type in additions.items():
        if column not in columns:
            if column == "event_time":
                # SQLite does not allow non-constant defaults such as
                # CURRENT_TIMESTAMP in ALTER TABLE ... ADD COLUMN. Add the
                # column without a default, then backfill legacy rows.
                conn.execute(
                    f"ALTER TABLE audit_log ADD COLUMN {column} {sql_type}"
                )
                conn.execute(
                    "UPDATE audit_log SET event_time = CURRENT_TIMESTAMP "
                    "WHERE event_time IS NULL"
                )
            elif column == "event_type":
                # A constant default is valid for ADD COLUMN and gives old
                # rows a meaningful legacy event type.
                conn.execute(
                    f"ALTER TABLE audit_log ADD COLUMN {column} {sql_type} "
                    "DEFAULT 'LEGACY'"
                )
            else:
                conn.execute(
                    f"ALTER TABLE audit_log ADD COLUMN {column} {sql_type}"
                )
    if owns_transaction:
        conn.commit()


def ensure_audit_table(conn) -> None:
    migrate_audit_table(conn)

def record_event(
    conn,
    event_type: str,
    description: str = "",
    username: Optional[str] = None,
    reference_type: Optional[str] = None,
    reference_id: Optional[Any] = None,
    details: Optional[dict] = None,
) -> int:
    """Write one audit event and return its row id."""
    owns_transaction = not conn.in_transaction
    ensure_audit_table(conn)
    payload = json.dumps(details or {}, ensure_ascii=False, default=str)
    cur = conn.execute(
        """INSERT INTO audit_log
           (event_time, username, event_type, description,
            reference_type, reference_id, details_json)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            datetime.now().isoformat(timespec="seconds"),
            username,
            event_type,
            description,
            reference_type,
            None if reference_id is None else str(reference_id),
            payload,
        ),
    )
    # Standalone audit calls remain durable, while business-transaction audit
    # events stay inside the caller transaction and roll back with it.
    if owns_transaction:
        conn.commit()
    return int(cur.lastrowid)

def recent_events(conn, limit: int = 100):
    """Return recent audit events, newest first."""
    ensure_audit_table(conn)
    limit = max(1, min(int(limit), 1000))
    return conn.execute(
        """SELECT id, event_time, username, event_type, description,
                  reference_type, reference_id, details_json
           FROM audit_log
           ORDER BY id DESC LIMIT ?""",
        (limit,),
    ).fetchall()


def record_business_event(
    conn,
    event_type: str,
    *,
    username: Optional[str] = None,
    reference_type: Optional[str] = None,
    reference_id: Optional[Any] = None,
    description: str = "",
    details: Optional[dict] = None,
) -> int:
    """Record a standardized completed business event."""
    return record_event(
        conn,
        event_type=event_type,
        description=description,
        username=username,
        reference_type=reference_type,
        reference_id=reference_id,
        details=details,
    )
