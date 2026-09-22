"""BKPOS Phase 54 — database index health and optimization helpers.

Read-only inspection helpers for the indexes introduced by the Phase 54
migration.  They never create, drop, or modify indexes themselves.
"""
from __future__ import annotations

from services.performance_tools import table_indexes

RECOMMENDED_INDEXES = {
    "products": ("idx_products_barcode",),
    "sales_history": ("idx_sales_history_timestamp",),
    "sale_items": ("idx_sale_items_sale_id",),
    "grn_headers": ("idx_grn_headers_supplier_id", "idx_grn_headers_supplier_account"),
    "grn_items": ("idx_grn_items_grn_id",),
    "stock_movements": ("idx_stock_movements_barcode_time",),
    "branch_stock": ("idx_branch_stock_branch_barcode",),
    "customer_account_transactions": ("idx_customer_account_tx_customer",),
    "customer_account_invoices": ("idx_customer_account_invoice_customer",),
    "supplier_payments": ("idx_supplier_payments_supplier",),
    "supplier_credits": ("idx_supplier_credits_supplier",),
    "account_transactions": ("idx_account_transactions_account_type",),
    "audit_log": ("idx_audit_log_event_time", "idx_audit_log_event_type"),
    "management_alerts": ("idx_management_alerts_status",),
    "cashier_shifts": ("idx_cashier_shifts_status",),
    "cashup_records": ("idx_cashup_records_date",),
    "return_history": ("idx_return_history_timestamp",),
    "return_items": ("idx_return_items_return_id",),
    "loyalty_transactions": ("idx_loyalty_transactions_customer", "idx_loyalty_transactions_sale"),
}


def index_health(conn) -> dict:
    """Return missing/available Phase 54 indexes without changing the DB."""
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    available = []
    missing = []
    for table, indexes in RECOMMENDED_INDEXES.items():
        if table not in tables:
            continue
        names = {x["name"] for x in table_indexes(conn, table)}
        for index in indexes:
            (available if index in names else missing).append(index)
    return {
        "ok": not missing,
        "available": sorted(available),
        "missing": sorted(missing),
        "checked_tables": sorted(t for t in RECOMMENDED_INDEXES if t in tables),
    }
