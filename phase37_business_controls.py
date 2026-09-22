"""Phase 37 business-control and release validation checks."""
from __future__ import annotations
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# If a table exists, at least one of the listed date columns must exist.
DATE_COLUMNS = {
    "sales_history": ("timestamp",),
    "grn_headers": ("created_at", "grn_date", "date"),
    "return_history": ("timestamp",),
    "credit_notes": ("timestamp", "credit_date", "date"),
    "supplier_credits": ("credit_date", "created_at"),
    "customer_account_payments": ("payment_date", "date", "timestamp"),
    "supplier_payments": ("payment_date", "date", "timestamp"),
}

def validate_database_schema(conn: sqlite3.Connection) -> list[str]:
    problems=[]
    tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for table, candidates in DATE_COLUMNS.items():
        if table not in tables:
            continue
        cols={r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if not any(c in cols for c in candidates):
            problems.append(f"{table}: missing supported date column ({', '.join(candidates)})")
    return problems

def validate_history_source() -> list[str]:
    p=BASE_DIR / "history.py"
    text=p.read_text(encoding="utf-8")
    problems=[]
    # This was the Phase 32 regression that caused the real-world error.
    if "customer_account_payments.created_at" in text:
        problems.append("history.py still references customer_account_payments.created_at")
    return problems

def run(db_path: str | None = None) -> None:
    problems=validate_history_source()
    if db_path:
        con=sqlite3.connect(db_path)
        try: problems.extend(validate_database_schema(con))
        finally: con.close()
    if problems:
        raise RuntimeError("; ".join(problems))

if __name__ == "__main__":
    run()
    print("PHASE 37 BUSINESS CONTROL CHECK: PASS")
