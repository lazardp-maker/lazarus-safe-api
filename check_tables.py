import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "lazarus_safe_v2.db"


def main():
    print(f"DB file: {DB_PATH}")
    print(f"Exists: {DB_PATH.exists()}")

    if not DB_PATH.exists():
        print("Database file not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        ORDER BY name
    """)
    tables = cursor.fetchall()

    if not tables:
        print("NO TABLES FOUND")
        conn.close()
        return

    print("\nTABLES:")
    for table in tables:
        table_name = table["name"]
        cursor.execute(f"SELECT COUNT(*) AS total FROM {table_name}")
        total = cursor.fetchone()["total"]
        print(f"- {table_name}: {total} rows")

    conn.close()
    print("\nCheck completed successfully.")


if __name__ == "__main__":
    main()