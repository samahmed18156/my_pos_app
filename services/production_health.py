"""Read-only production health diagnostics for BKPOS (Phase 50)."""
from __future__ import annotations
import os, sqlite3, sys, time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

@dataclass
class HealthCheck:
    name: str
    status: str
    message: str
    duration_ms: float = 0.0
    details: dict[str, Any] | None = None

def _check(name, fn):
    start=time.perf_counter()
    try:
        result=fn()
        status, message, details = result if isinstance(result, tuple) else ("OK", str(result), {})
        return HealthCheck(name,status,message,(time.perf_counter()-start)*1000,details or {})
    except Exception as exc:
        return HealthCheck(name,"ERROR",f"{type(exc).__name__}: {exc}",(time.perf_counter()-start)*1000,{})

def check_database(conn):
    try:
        row=conn.execute("PRAGMA integrity_check").fetchone(); result=row[0] if row else "unknown"
    except sqlite3.DatabaseError as exc:
        return "ERROR", f"SQLite database error: {exc}", {"error":str(exc)}
    if str(result).lower() != "ok": return "ERROR", f"SQLite integrity_check: {result}", {"result":result}
    fk=conn.execute("PRAGMA foreign_key_check").fetchall()
    if fk: return "ERROR", f"{len(fk)} foreign-key violation(s)", {"violations":[tuple(x) for x in fk[:20]]}
    return "OK", "Database integrity and foreign keys are OK", {"foreign_key_violations":0}

def check_required_tables(conn):
    required={"products","sales_history","sale_items","stock_movements","grns","grn_items"}
    actual={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    missing=sorted(required-actual)
    if missing: return "ERROR", f"Missing required table(s): {', '.join(missing)}", {"missing":missing}
    return "OK", "Required business tables are present", {"required_count":len(required)}

def check_database_path(path):
    p=Path(path)
    if not p.exists(): return "ERROR", f"Database file does not exist: {p}", {"path":str(p)}
    if not p.is_file(): return "ERROR", f"Database path is not a file: {p}", {"path":str(p)}
    if not os.access(p,os.R_OK): return "ERROR", "Database file is not readable", {"path":str(p)}
    return "OK", "Database file is present and readable", {"path":str(p),"size_bytes":p.stat().st_size}

def run_health_check(conn=None, db_path=None):
    own=conn is None
    if own:
        if db_path is None: raise ValueError("db_path is required when conn is not supplied")
        conn=sqlite3.connect(str(db_path)); conn.execute("PRAGMA foreign_keys=ON")
    try:
        checks=[]
        if db_path is not None: checks.append(_check("database_file",lambda:check_database_path(db_path)))
        checks += [_check("database_integrity",lambda:check_database(conn)), _check("required_tables",lambda:check_required_tables(conn))]
        errors=sum(c.status=="ERROR" for c in checks); warnings=sum(c.status=="WARN" for c in checks)
        return {"phase":50,"overall":"ERROR" if errors else ("WARN" if warnings else "OK"),"checks":[asdict(c) for c in checks],"python":sys.version.split()[0],"read_only":True}
    finally:
        if own: conn.close()
