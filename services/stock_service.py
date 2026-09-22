"""Canonical stock movement service for the current BKPOS schema.

All callers should record movements using a barcode and a signed quantity.
A sale therefore records a negative quantity; a GRN/return records a positive
quantity. The optional connection parameter lets the movement share the
caller's transaction instead of committing independently.
"""
import sqlite3
from core.config import DB_PATH


def record_stock_movement(barcode, movement_type, quantity, reference='',
                          description='', qty_before=None, qty_after=None,
                          cost_price=0.0, reason='', cashier='Unknown', conn=None):
    own_connection = conn is None
    db = conn or sqlite3.connect(DB_PATH)
    try:
        if qty_before is None or qty_after is None:
            row = db.execute("SELECT COALESCE(soh,0), COALESCE(description,''), COALESCE(cost_price,0) FROM products WHERE barcode=?", (barcode,)).fetchone()
            if row is None:
                raise ValueError(f"Unknown product barcode: {barcode}")
            current_soh, product_description, product_cost = row
            qty_before = float(current_soh) - float(quantity)
            qty_after = float(current_soh)
            if not description:
                description = product_description
            if not cost_price:
                cost_price = product_cost
        cols = {r[1] for r in db.execute("PRAGMA table_info(stock_movements)")}
        if {"barcode", "qty", "qty_before", "qty_after"}.issubset(cols):
            # Older databases can retain the legacy NOT NULL `quantity` column
            # alongside the canonical `qty` column. Populate both when it exists.
            if "quantity" in cols:
                db.execute("""INSERT INTO stock_movements
                    (timestamp, barcode, description, movement_type, qty, quantity,
                     qty_before, qty_after, cost_price, reference, reason, cashier)
                    VALUES(datetime('now','localtime'),?,?,?,?,?,?,?,?,?,?,?)""",
                    (barcode, description, movement_type, float(quantity), float(quantity),
                     float(qty_before), float(qty_after), float(cost_price or 0),
                     reference, reason, cashier))
            else:
                db.execute("""INSERT INTO stock_movements
                    (timestamp, barcode, description, movement_type, qty, qty_before,
                     qty_after, cost_price, reference, reason, cashier)
                    VALUES(datetime('now','localtime'),?,?,?,?,?,?,?,?,?,?)""",
                    (barcode, description, movement_type, float(quantity),
                     float(qty_before), float(qty_after), float(cost_price or 0),
                     reference, reason, cashier))
        elif {"product_id", "quantity", "created_at"}.issubset(cols):
            product = db.execute("SELECT rowid FROM products WHERE barcode=?", (barcode,)).fetchone()
            if not product:
                raise ValueError(f"Unknown product barcode: {barcode}")
            db.execute("""INSERT INTO stock_movements(product_id,movement_type,quantity,reference,created_at)
                         VALUES(?,?,?,?,datetime('now','localtime'))""",
                       (product[0], movement_type, float(quantity), reference))
        else:
            raise RuntimeError("Unsupported stock_movements schema.")
        if own_connection:
            db.commit()
    except Exception:
        if own_connection:
            db.rollback()
        raise
    finally:
        if own_connection:
            db.close()
