"""Concurrency-safe document number allocation for BKPOS."""

_ALLOWED_TABLES = {"sale": "sales_history", "grn": "grn_headers", "transfer": "stock_transfers", "return": "return_history", "supplier_credit": "supplier_credits", "po": "purchase_orders"}


def next_document_number(conn, kind: str, prefix: str) -> str:
    table_name = _ALLOWED_TABLES.get(kind)
    if table_name is None:
        raise ValueError(f"Unsupported document sequence: {kind!r}")
    conn.execute("""CREATE TABLE IF NOT EXISTS document_sequences(
        sequence_key TEXT PRIMARY KEY,
        last_number INTEGER NOT NULL DEFAULT 0
    )""")
    conn.execute(
        "INSERT OR IGNORE INTO document_sequences(sequence_key,last_number) "
        f"SELECT ?, COALESCE(MAX(id),0) FROM {table_name}", (kind,)
    )
    conn.execute("UPDATE document_sequences SET last_number=last_number+1 WHERE sequence_key=?", (kind,))
    value = conn.execute("SELECT last_number FROM document_sequences WHERE sequence_key=?", (kind,)).fetchone()[0]
    return f"{prefix}-{int(value):06d}"
