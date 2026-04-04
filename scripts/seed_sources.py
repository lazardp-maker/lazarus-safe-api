import sqlite3
from scripts.init_db import DB_PATH

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
    {
        "name": "MAI",
        "source_type": "official",
        "base_url": "https://www.mai.gov.ro",
        "county": None,
        "city": None,
        "trust_level": 5,
        "is_active": 1,
    },

    # ===== SURSE OFICIALE LOCALE =====
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
    {
        "name": "IPJ Bucuresti",
        "source_type": "official",
        "base_url": "https://b.politiaromana.ro",
        "county": "bucuresti",
        "city": None,
        "trust_level": 5,
        "is_active": 1,
    },
    {
        "name": "ISU Bucuresti-Ilfov",
        "source_type": "official",
        "base_url": "https://isubif.ro",
        "county": "bucuresti",
        "city": "bucuresti",
        "trust_level": 5,
        "is_active": 1,
    },
    {
        "name": "IPJ Cluj",
        "source_type": "official",
        "base_url": "https://cj.politiaromana.ro",
        "county": "cluj",
        "city": None,
        "trust_level": 5,
        "is_active": 1,
    },
    {
        "name": "IPJ Timis",
        "source_type": "official",
        "base_url": "https://tm.politiaromana.ro",
        "county": "timis",
        "city": None,
        "trust_level": 5,
        "is_active": 1,
    },
    {
        "name": "IPJ Iasi",
        "source_type": "official",
        "base_url": "https://is.politiaromana.ro",
        "county": "iasi",
        "city": None,
        "trust_level": 5,
        "is_active": 1,
    },
    {
        "name": "IPJ Constanta",
        "source_type": "official",
        "base_url": "https://ct.politiaromana.ro",
        "county": "constanta",
        "city": None,
        "trust_level": 5,
        "is_active": 1,
    },

    # ===== PRESA LOCALA / REGIONALA =====
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
    {
        "name": "Cluj24",
        "source_type": "press",
        "base_url": "https://cluj24.ro",
        "county": "cluj",
        "city": None,
        "trust_level": 4,
        "is_active": 1,
    },
    {
        "name": "Opinia Timisoarei",
        "source_type": "press",
        "base_url": "https://www.opiniatimisoarei.ro",
        "county": "timis",
        "city": None,
        "trust_level": 4,
        "is_active": 1,
    },
    {
        "name": "Ziarul de Iasi",
        "source_type": "press",
        "base_url": "https://www.ziaruldeiasi.ro",
        "county": "iasi",
        "city": None,
        "trust_level": 4,
        "is_active": 1,
    },
    {
        "name": "Replica Online",
        "source_type": "press",
        "base_url": "https://www.replicaonline.ro",
        "county": "constanta",
        "city": None,
        "trust_level": 4,
        "is_active": 1,
    },

    # ===== PRESA NATIONALA =====
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
    {
        "name": "HotNews",
        "source_type": "press",
        "base_url": "https://hotnews.ro",
        "county": None,
        "city": None,
        "trust_level": 3,
        "is_active": 1,
    },
    {
        "name": "Antena 3 CNN",
        "source_type": "press",
        "base_url": "https://www.antena3.ro",
        "county": None,
        "city": None,
        "trust_level": 3,
        "is_active": 1,
    },
]

INSERT_SQL = """
INSERT OR IGNORE INTO sources (
    name,
    source_type,
    base_url,
    county,
    city,
    trust_level,
    is_active
)
VALUES (?, ?, ?, ?, ?, ?, ?);
"""


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()

        rows = [
            (
                source["name"],
                source["source_type"],
                source["base_url"],
                source["county"],
                source["city"],
                source["trust_level"],
                source["is_active"],
            )
            for source in SOURCES
        ]

        cursor.executemany(INSERT_SQL, rows)
        conn.commit()

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM sources
        """)
        total = cursor.fetchone()[0]

        print(f"sources seeded")
        print(f"total sources in db: {total}")
        print(f"db path: {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()