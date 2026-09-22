from core.config import DB_PATH
import sqlite3


def fix_branches_table():

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("Checking branches table...")

    # Show the current structure
    cursor.execute("PRAGMA table_info(branches)")
    columns = cursor.fetchall()

    if not columns:
        print("No branches table found.")
        print("Creating a new one...")

        cursor.execute("""
            CREATE TABLE branches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                branch_name TEXT NOT NULL,
                branch_code TEXT UNIQUE NOT NULL,
                address TEXT,
                phone TEXT,
                status TEXT DEFAULT 'Active'
            )
        """)

        conn.commit()
        conn.close()

        print("SUCCESS: Branches table created.")
        return

    print("\nCurrent branches columns:")

    for column in columns:
        print("-", column[1])

    column_names = [column[1] for column in columns]

    # Check whether our new structure already exists
    required_columns = [
        "branch_name",
        "branch_code",
        "address",
        "phone",
        "status"
    ]

    missing_columns = []

    for column in required_columns:
        if column not in column_names:
            missing_columns.append(column)

    if not missing_columns:

        print("\nBranches table is already correct.")
        conn.close()
        return

    print("\nMissing columns:")
    for column in missing_columns:
        print("-", column)

    print("\nAdding missing columns...")

    # Add missing columns one by one
    for column in missing_columns:

        if column == "branch_name":
            cursor.execute(
                "ALTER TABLE branches ADD COLUMN branch_name TEXT"
            )

        elif column == "branch_code":
            cursor.execute(
                "ALTER TABLE branches ADD COLUMN branch_code TEXT"
            )

        elif column == "address":
            cursor.execute(
                "ALTER TABLE branches ADD COLUMN address TEXT"
            )

        elif column == "phone":
            cursor.execute(
                "ALTER TABLE branches ADD COLUMN phone TEXT"
            )

        elif column == "status":
            cursor.execute(
                "ALTER TABLE branches ADD COLUMN status TEXT DEFAULT 'Active'"
            )

    conn.commit()

    print("\nSUCCESS!")
    print("The branches table has been updated.")

    # Show final structure
    cursor.execute("PRAGMA table_info(branches)")
    columns = cursor.fetchall()

    print("\nFinal branches columns:")

    for column in columns:
        print("-", column[1], "(", column[2], ")")

    conn.close()


if __name__ == "__main__":
    fix_branches_table()