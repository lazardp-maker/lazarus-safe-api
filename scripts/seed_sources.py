import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "lazarus_safe_v2.db"

SOURCES = [
    ("Politia Romana", "official", "https://www.politiaromana.ro", None, None, 5),
    ("DSU", "official", "https://www.dsu.mai.gov.ro", None, None, 5),
    ("IPJ Arges", "official", "https://ag.politiaromana.ro", "arges", None, 5),
    ("ISU Arges", "official", "https://www.isuarges.ro", "arges", None, 5),
]

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    for row in SOURCES:
        cursor.execute("""
            INSERT INTO sources (name, source_type, base_url, county, city, trust_level)
            VALUES (?, ?, ?, ?, ?, ?)
        """, row)

    conn.commit()
    conn.close()
    print("Sources seeded successfully.")

if __name__ == "__main__":
    main()


