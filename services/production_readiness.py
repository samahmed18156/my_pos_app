"""Read-only production readiness diagnostics for BKPOS.

The checks in this module never modify the database. They are intended for
pre-release verification and can safely be run against a copy of the live DB.
"""
from __future__ import annotations
import os
import sqlite3
from pathlib import Path

CORE_TABLES = {
    "users", "products", "branches", "stock_movements", "sales_history",
    "sale_items", "customers", "account_transactions", "grn_headers", "grn_items",
}


def _tables(con):
    return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _columns(con, table):
    return {r[1] for r in con.execute(f'PRAGMA table_info("{table}")')}


def database_readiness(db_path: str | os.PathLike) -> dict:
    """Return a detailed, read-only health report for a BKPOS database."""
    path = Path(db_path)
    result = {
        "exists": path.is_file(),
        "integrity": False,
        "missing_tables": [],
        "missing_columns": {},
        "negative_global_stock": [],
        "negative_branch_stock": [],
        "orphan_sale_items": 0,
        "orphan_grn_items": 0,
        "orphan_stock_movements": 0,
        "ok": False,
    }
    if not result["exists"]:
        return result

    con = sqlite3.connect(str(path))
    try:
        result["integrity"] = con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        if not result["integrity"]:
            return result
        tables = _tables(con)
        result["missing_tables"] = sorted(CORE_TABLES - tables)

        required = {
            "products": {"barcode", "description", "selling_price", "cost_price", "soh"},
            "sales_history": {"id", "total_amount", "total_cost", "payment_type"},
            "sale_items": {"sale_id", "barcode", "qty", "price", "value", "cost_price"},
            "stock_movements": {"barcode", "movement_type", "qty", "qty_before", "qty_after"},
            "grn_headers": {"id", "grn_no", "supplier_id", "subtotal", "vat", "total"},
            "grn_items": {"grn_id", "barcode", "qty_received", "cost_price", "value"},
        }
        for table, needed in required.items():
            if table in tables:
                missing = sorted(needed - _columns(con, table))
                if missing:
                    result["missing_columns"][table] = missing

        if "products" in tables:
            result["negative_global_stock"] = [r[0] for r in con.execute(
                "SELECT barcode FROM products WHERE COALESCE(soh,0) < -0.000001 ORDER BY barcode")]
        if "branch_stock" in tables and "products" in tables:
            cols = _columns(con, "branch_stock")
            if {"barcode", "soh"}.issubset(cols):
                result["negative_branch_stock"] = [r[0] for r in con.execute(
                    "SELECT barcode FROM branch_stock WHERE COALESCE(soh,0) < -0.000001 ORDER BY barcode")]

        if {"sale_items", "sales_history"}.issubset(tables):
            result["orphan_sale_items"] = con.execute(
                "SELECT COUNT(*) FROM sale_items i LEFT JOIN sales_history s ON s.id=i.sale_id WHERE s.id IS NULL").fetchone()[0]
        if {"grn_items", "grn_headers"}.issubset(tables):
            result["orphan_grn_items"] = con.execute(
                "SELECT COUNT(*) FROM grn_items i LEFT JOIN grn_headers h ON h.id=i.grn_id WHERE h.id IS NULL").fetchone()[0]
        if "stock_movements" in tables and "products" in tables:
            result["orphan_stock_movements"] = con.execute(
                "SELECT COUNT(*) FROM stock_movements m LEFT JOIN products p ON p.barcode=m.barcode WHERE m.barcode IS NOT NULL AND p.barcode IS NULL").fetchone()[0]
    finally:
        con.close()

    result["ok"] = (
        result["integrity"] and not result["missing_tables"] and
        not result["missing_columns"] and not result["negative_global_stock"] and
        not result["negative_branch_stock"] and result["orphan_sale_items"] == 0 and
        result["orphan_grn_items"] == 0 and result["orphan_stock_movements"] == 0
    )
    return result


def jasper_runtime_readiness(runtime_dir: str | os.PathLike) -> dict:
    """Verify the bundled Jasper runtime has the core viewer and main JAR."""
    root = Path(runtime_dir)
    main = root / "jasperreports-6.21.3.jar"
    metadata = root / "jasperreports-metadata-6.21.3.jar"
    return {
        "directory": str(root),
        "exists": root.is_dir(),
        "main_jar": main.is_file() and main.stat().st_size > 1000000,
        "metadata_jar": metadata.is_file() and metadata.stat().st_size > 1000,
        "ok": root.is_dir() and main.is_file() and main.stat().st_size > 1000000 and metadata.is_file() and metadata.stat().st_size > 1000,
    }
