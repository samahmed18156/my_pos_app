"""Multi-branch operations and safe synchronization helpers for BKPOS.

Synchronization is deliberately conservative: bundles are exports of branch state
and transfer history. Imports stage a snapshot for comparison rather than silently
overwriting live stock. This prevents two branches from destroying each other's
inventory when both have been operating offline.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from core.config import DB_PATH
from services.branch_stock_service import ensure_schema


def ensure_schema_v9(conn):
    ensure_schema(conn)
    conn.execute("""CREATE TABLE IF NOT EXISTS branch_sync_batches(
        batch_id TEXT PRIMARY KEY,
        branch_id INTEGER NOT NULL,
        exported_at TEXT NOT NULL,
        imported_from TEXT,
        status TEXT NOT NULL DEFAULT 'EXPORTED')""")
    conn.execute("""CREATE TABLE IF NOT EXISTS branch_sync_staging(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id TEXT NOT NULL,
        branch_id INTEGER NOT NULL,
        barcode TEXT NOT NULL,
        description TEXT,
        remote_soh REAL NOT NULL,
        local_soh REAL,
        variance REAL,
        imported_at TEXT NOT NULL,
        UNIQUE(batch_id, branch_id, barcode))""")
    conn.commit()


def branch_overview(conn):
    ensure_schema_v9(conn)
    rows = conn.execute("""
        SELECT b.id, b.branch_name, b.branch_code, COALESCE(b.status,'Active'),
               COUNT(bs.barcode), COALESCE(SUM(bs.soh),0)
        FROM branches b
        LEFT JOIN branch_stock bs ON bs.branch_id=b.id
        GROUP BY b.id, b.branch_name, b.branch_code, b.status
        ORDER BY b.id
    """).fetchall()
    return [dict(id=r[0], name=r[1], code=r[2], status=r[3], products=int(r[4]), units=float(r[5] or 0)) for r in rows]


def transfer_history(conn, *, limit=100, branch_id=None):
    ensure_schema_v9(conn)
    where, args = "", []
    if branch_id is not None:
        where = " WHERE from_branch=? OR to_branch=?"
        args = [int(branch_id), int(branch_id)]
    rows = conn.execute(f"""
        SELECT st.id, st.transfer_no, st.from_branch, fb.branch_name,
               st.to_branch, tb.branch_name, st.barcode, st.description,
               st.qty, st.status, st.cashier, st.timestamp
        FROM stock_transfers st
        LEFT JOIN branches fb ON fb.id=st.from_branch
        LEFT JOIN branches tb ON tb.id=st.to_branch
        {where}
        ORDER BY st.id DESC LIMIT ?
    """, args + [int(limit)]).fetchall()
    return rows


def reconciliation(conn, branch_id):
    """Compare branch stock to the sum of all branch stock for each SKU."""
    ensure_schema_v9(conn)
    bid = int(branch_id)
    rows = conn.execute("""
        SELECT p.barcode, p.description, COALESCE(bs.soh,0), COALESCE(p.soh,0),
               COALESCE((SELECT SUM(x.soh) FROM branch_stock x WHERE x.barcode=p.barcode),0)
        FROM products p
        LEFT JOIN branch_stock bs ON bs.barcode=p.barcode AND bs.branch_id=?
        ORDER BY p.barcode
    """, (bid,)).fetchall()
    return [
        dict(barcode=r[0], description=r[1], branch_soh=float(r[2]), global_soh=float(r[3]),
             branch_total=float(r[4]), variance=round(float(r[3])-float(r[4]), 6))
        for r in rows if abs(float(r[3])-float(r[4])) > 1e-6
    ]


def export_bundle(conn, branch_id, path):
    ensure_schema_v9(conn)
    bid = int(branch_id)
    branch = conn.execute("SELECT id,branch_name,branch_code FROM branches WHERE id=?", (bid,)).fetchone()
    if not branch:
        raise ValueError("Branch was not found.")
    products = conn.execute("""
        SELECT bs.barcode, p.description, bs.soh
        FROM branch_stock bs LEFT JOIN products p ON p.barcode=bs.barcode
        WHERE bs.branch_id=? ORDER BY bs.barcode
    """, (bid,)).fetchall()
    transfers = conn.execute("""
        SELECT transfer_no,from_branch,to_branch,barcode,description,qty,status,cashier,timestamp
        FROM stock_transfers WHERE from_branch=? OR to_branch=? ORDER BY id
    """, (bid, bid)).fetchall()
    batch_id = uuid.uuid4().hex
    exported_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    payload = {
        "format": "BKPOS_BRANCH_SYNC_V1", "batch_id": batch_id,
        "exported_at": exported_at,
        "branch": {"id": branch[0], "name": branch[1], "code": branch[2]},
        "stock": [{"barcode": r[0], "description": r[1], "soh": float(r[2])} for r in products],
        "transfers": [dict(zip(("transfer_no","from_branch","to_branch","barcode","description","qty","status","cashier","timestamp"), r)) for r in transfers],
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    conn.execute("INSERT INTO branch_sync_batches(batch_id,branch_id,exported_at,status) VALUES(?,?,?,'EXPORTED')", (batch_id,bid,exported_at))
    conn.commit()
    return batch_id


def import_bundle(conn, path):
    ensure_schema_v9(conn)
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("format") != "BKPOS_BRANCH_SYNC_V1":
        raise ValueError("Unsupported BKPOS branch sync bundle.")
    batch_id = str(payload.get("batch_id") or "").strip()
    branch = payload.get("branch") or {}
    bid = int(branch.get("id"))
    if not batch_id or bid <= 0:
        raise ValueError("Invalid branch sync bundle metadata.")
    if conn.execute("SELECT 1 FROM branch_sync_batches WHERE batch_id=?", (batch_id,)).fetchone():
        return {"batch_id": batch_id, "duplicate": True, "rows": 0, "conflicts": 0}
    rows = 0; conflicts = 0
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    for item in payload.get("stock", []):
        code = str(item.get("barcode", "")).strip()
        if not code: continue
        remote = float(item.get("soh", 0) or 0)
        local_row = conn.execute("SELECT soh FROM branch_stock WHERE branch_id=? AND barcode=?", (bid,code)).fetchone()
        local = float(local_row[0]) if local_row else None
        variance = None if local is None else remote-local
        if variance is not None and abs(variance) > 1e-6: conflicts += 1
        conn.execute("INSERT INTO branch_sync_staging(batch_id,branch_id,barcode,description,remote_soh,local_soh,variance,imported_at) VALUES(?,?,?,?,?,?,?,?)",
                     (batch_id,bid,code,item.get("description"),remote,local,variance,now))
        rows += 1
    conn.execute("INSERT INTO branch_sync_batches(batch_id,branch_id,exported_at,imported_from,status) VALUES(?,?,?,?, 'STAGED')",
                 (batch_id,bid,str(payload.get("exported_at") or ""),str(path)))
    conn.commit()
    return {"batch_id": batch_id, "duplicate": False, "rows": rows, "conflicts": conflicts}


def staged_conflicts(conn, batch_id=None):
    ensure_schema_v9(conn)
    where = "WHERE ABS(COALESCE(variance,0)) > 0.000001"; args=[]
    if batch_id:
        where += " AND batch_id=?"; args.append(batch_id)
    return conn.execute(f"SELECT batch_id,branch_id,barcode,description,remote_soh,local_soh,variance,imported_at FROM branch_sync_staging {where} ORDER BY id DESC", args).fetchall()
