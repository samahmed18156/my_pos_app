"""Central store/company settings for the POS."""
import sqlite3
import os

from core.config import DB_PATH
DB_NAME = DB_PATH
DEFAULT_STORE_NAME = "FAMILY SUPERMARKET"

def _connect():
    return sqlite3.connect(DB_NAME)

def ensure_settings():
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pos_settings (
            setting_key TEXT PRIMARY KEY,
            setting_value TEXT NOT NULL
        )
    """)
    conn.execute(
        "INSERT OR IGNORE INTO pos_settings(setting_key, setting_value) VALUES (?, ?)",
        ("store_name", DEFAULT_STORE_NAME),
    )
    conn.commit()
    conn.close()

def get_store_name():
    try:
        ensure_settings()
        conn = _connect()
        row = conn.execute(
            "SELECT setting_value FROM pos_settings WHERE setting_key='store_name'"
        ).fetchone()
        conn.close()
        return (row[0].strip() if row and row[0] else DEFAULT_STORE_NAME)
    except Exception:
        return DEFAULT_STORE_NAME

def set_store_name(name):
    name = str(name).strip()
    if not name:
        raise ValueError("Store name cannot be empty.")
    ensure_settings()
    conn = _connect()
    conn.execute(
        "INSERT OR REPLACE INTO pos_settings(setting_key, setting_value) VALUES (?, ?)",
        ("store_name", name),
    )
    conn.commit()
    conn.close()
    return name
