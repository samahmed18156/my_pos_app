
"""BKPOS Phase 53 performance helpers.

Read-only utilities for measuring query plans, timing operations and checking
that commonly-used SQLite columns have useful indexes. They do not alter
business data.
"""
from __future__ import annotations
import sqlite3
import time
from dataclasses import dataclass
from typing import Callable, Any

@dataclass(frozen=True)
class Timing:
    name: str
    elapsed_ms: float
    result_count: int | None = None

def time_call(name: str, fn: Callable[[], Any]) -> tuple[Any, Timing]:
    start = time.perf_counter()
    result = fn()
    elapsed = (time.perf_counter() - start) * 1000
    count = None
    try:
        count = len(result)
    except Exception:
        count = None
    return result, Timing(name, elapsed, count)

def explain_query(conn: sqlite3.Connection, sql: str, params=()):
    """Return SQLite's query plan without modifying the database."""
    return conn.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall()

def table_indexes(conn: sqlite3.Connection, table: str) -> list[dict]:
    rows = conn.execute(f"PRAGMA index_list({table!r})").fetchall()
    return [
        {"name": r[1], "unique": bool(r[2]), "origin": r[3]}
        for r in rows
    ]

def benchmark_query(conn: sqlite3.Connection, sql: str, params=(),
                    repeats: int = 5) -> Timing:
    if repeats < 1:
        raise ValueError("repeats must be at least 1")
    start = time.perf_counter()
    last = None
    for _ in range(repeats):
        last = conn.execute(sql, params).fetchall()
    elapsed = (time.perf_counter() - start) * 1000 / repeats
    return Timing("query", elapsed, len(last) if last is not None else 0)
