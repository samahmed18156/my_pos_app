from core.config import DB_PATH
import sqlite3


def fix_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check what's in the table now
    cursor.execute("PRAGMA table_info(sales_history)")
    columns = cursor.fetchall()
    col_names = [col[1] for col in columns]

    print(f"Current columns: {col_names}")

    # If timestamp is missing, we need to rebuild the table
    if "timestamp" not in col_names:
        print("⚠️ timestamp column is missing - rebuilding sales_history table...")

        # Create a new table with the right structure
        cursor.execute("""
            CREATE TABLE sales_history_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                total_amount REAL,
                total_cost REAL,
                payment_type TEXT
            )
        """)

        # Copy any existing data (if any)
        try:
            cursor.execute("""
                INSERT INTO sales_history_new (id, total_amount)
                SELECT id, total_amount FROM sales_history
            """)
            print("✅ Copied existing data")
        except:
            print("ℹ️ No existing data to copy")

        # Drop old table and rename new one
        cursor.execute("DROP TABLE sales_history")
        cursor.execute("ALTER TABLE sales_history_new RENAME TO sales_history")

        print("✅ Rebuilt sales_history table with correct columns!")

    conn.commit()
    conn.close()

    # Verify
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(sales_history)")
    columns = cursor.fetchall()
    print("\n✅ Final columns in sales_history:")
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")
    conn.close()


if __name__ == "__main__":
    fix_database()