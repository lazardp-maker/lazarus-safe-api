import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "lazarus_safe_v2.db"

SOURCES = [
    # ===== SURSE OFICIALE NATIONALE =====
    {
        "name": "Politia Romana",
        "source_type": "official",
        "base_url": "https://www.politiaromana.ro",
        "county": None,
        "city": None,
        "trust_level": 5,
        "is_active": 1,
    },
    {
        "name": "DSU",
        "source_type": "official",
        "base_url": "https://www.dsu.mai.gov.ro",
        "county": None,
        "city": None,
        "trust_level": 5,
        "is_active": 1,
    },
    {
        "name": "IGSU",
        "source_type": "official",
        "base_url": "https://www.igsu.ro",
        "county": None,
        "city": None,
        "trust_level": 5,
        "is_active": 1,
    },

    # ===== SURSE OFICIALE LOCALE - ARGES =====
    {
        "name": "IPJ Arges",
        "source_type": "official",
        "base_url": "https://ag.politiaromana.ro",
        "county": "arges",
        "city": None,
        "trust_level": 5,
        "is_active": 1,
    },
    {
        "name": "ISU Arges",
        "source_type": "official",
        "base_url": "https://www.isuarges.ro",
        "county": "arges",
        "city": None,
        "trust_level": 5,
        "is_active": 1,
    },
    {
        "name": "Politia Locala Pitesti",
        "source_type": "official",
        "base_url": "https://www.primariapitesti.ro",
        "county": "arges",
        "city": "pitesti",
        "trust_level": 4,
        "is_active": 1,
    },

    # ===== PRESA LOCALA / REGIONALA - ARGES =====
    {
        "name": "Ziarul Argesul",
        "source_type": "press",
        "base_url": "https://ziarulargesul.ro",
        "county": "arges",
        "city": None,
        "trust_level": 4,
        "is_active": 1,
    },
    {
        "name": "Ancheta Online",
        "source_type": "press",
        "base_url": "https://anchetaonline.ro",
        "county": "arges",
        "city": None,
        "trust_level": 4,
        "is_active": 1,
    },
    {
        "name": "Jurnalul de Arges",
        "source_type": "press",
        "base_url": "https://jurnaluldearges.ro",
        "county": "arges",
        "city": None,
        "trust_level": 4,
        "is_active": 1,
    },
    {
        "name": "ePitesti",
        "source_type": "press",
        "base_url": "https://epitesti.ro",
        "county": "arges",
        "city": "pitesti",
        "trust_level": 4,
        "is_active": 1,
    },

    # ===== PRESA NATIONALA - BACKUP / COROBORARE =====
    {
        "name": "Agerpres",
        "source_type": "press",
        "base_url": "https://agerpres.ro",
        "county": None,
        "city": None,
        "trust_level": 5,
        "is_active": 1,
    },
    {
        "name": "Digi24",
        "source_type": "press",
        "base_url": "https://www.digi24.ro",
        "county": None,
        "city": None,
        "trust_level": 3,
        "is_active": 1,
    },
    {
        "name": "Stirile ProTV",
        "source_type": "press",
        "base_url": "https://stirileprotv.ro",
        "county": None,
        "city": None,
        "trust_level": 3,
        "is_active": 1,
    },
]

INSERT_SQL = """
INSERT INTO sources (
    name,
    source_type,
    base_url,
    county,
    city,
    trust_level,
    is_active
)
SELECT ?, ?, ?, ?, ?, ?, ?
WHERE NOT EXISTS (
    SELECT 1
    FROM sources
    WHERE lower(name) = lower(?)
      AND COALESCE(lower(county), '') = COALESCE(lower(?), '')
      AND COALESCE(lower(city), '') = COALESCE(lower(?), '')
);
"""

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    inserted = 0

    for source in SOURCES:
        cursor.execute(
            INSERT_SQL,
            (
                source["name"],
                source["source_type"],
                source["base_url"],
                source["county"],
                source["city"],
                source["trust_level"],
                source["is_active"],
                source["name"],
                source["county"],
                source["city"],
            )
        )

        if cursor.rowcount > 0:
            inserted += 1

    conn.commit()

    cursor.execute("""
        SELECT
            id, name, source_type, base_url, county, city, trust_level, is_active
        FROM sources
        ORDER BY trust_level DESC, source_type ASC, name ASC
    """)
    rows = cursor.fetchall()

    conn.close()

    print(f"Sources seed complete. Newly inserted: {inserted}")
    print("Current active source inventory:")
    for row in rows:
        print(row)

if __name__ == "__main__":
    main()

