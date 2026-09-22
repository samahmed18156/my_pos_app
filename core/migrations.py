"""Database migration manager for future schema upgrades."""
import sqlite3
from .config import DB_PATH

def run_migrations():
    conn=sqlite3.connect(DB_PATH)
    c=conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS schema_version(version INTEGER NOT NULL)')
    if c.execute('SELECT COUNT(*) FROM schema_version').fetchone()[0]==0:
        c.execute('INSERT INTO schema_version VALUES (0)')
    current=c.execute('SELECT version FROM schema_version').fetchone()[0]
    if current < 1:
        c.execute('''CREATE TABLE IF NOT EXISTS stock_movements(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER,
        movement_type TEXT NOT NULL,
        quantity REAL NOT NULL,
        reference TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        c.execute('UPDATE schema_version SET version=1')
    conn.commit(); conn.close()
