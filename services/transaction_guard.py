"""BKPOS Phase 48 — safe transaction boundaries.

Business services normally run inside the UI's transaction. This helper lets
service callers use the same contract safely, including nested operations.
Outer transactions are preserved; nested calls use SQLite SAVEPOINTs.
"""
from __future__ import annotations
from contextlib import contextmanager
import uuid

@contextmanager
def transaction(conn):
    """Run a block atomically without stealing an existing transaction.

    If the caller already has a transaction, a SAVEPOINT is used so an inner
    failure can be rolled back without discarding unrelated outer work.
    Otherwise this context owns BEGIN/COMMIT/ROLLBACK.
    """
    owns = not bool(getattr(conn, "in_transaction", False))
    name = f"bkpos_sp_{uuid.uuid4().hex}"
    if owns:
        conn.execute("BEGIN")
    else:
        conn.execute(f"SAVEPOINT {name}")
    try:
        yield conn
    except Exception:
        if owns:
            conn.rollback()
        else:
            conn.execute(f"ROLLBACK TO SAVEPOINT {name}")
            conn.execute(f"RELEASE SAVEPOINT {name}")
        raise
    else:
        if owns:
            conn.commit()
        else:
            conn.execute(f"RELEASE SAVEPOINT {name}")
