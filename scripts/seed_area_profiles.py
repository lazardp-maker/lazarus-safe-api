import sqlite3
from scripts.init_db import DB_PATH


AREA_RISK_PROFILES = [
    # ===== PROFILURI JUDEȚENE =====
    {
        "county": "arges",
        "city": "",
        "locality_type": "county",
        "crime_coefficient": 1.20,
        "violence_coefficient": 1.10,
        "theft_coefficient": 1.15,
        "traffic_coefficient": 1.00,
        "emergency_coefficient": 1.00,
        "source_note": "Profil județean Argeș",
    },
    {
        "county": "bucuresti",
        "city": "",
        "locality_type": "county",
        "crime_coefficient": 1.40,
        "violence_coefficient": 1.25,
        "theft_coefficient": 1.35,
        "traffic_coefficient": 1.10,
        "emergency_coefficient": 1.00,
        "source_note": "Profil județean București",
    },
    {
        "county": "cluj",
        "city": "",
        "locality_type": "county",
        "crime_coefficient": 1.15,
        "violence_coefficient": 1.05,
        "theft_coefficient": 1.10,
        "traffic_coefficient": 1.00,
        "emergency_coefficient": 1.00,
        "source_note": "Profil județean Cluj",
    },
    {
        "county": "timis",
        "city": "",
        "locality_type": "county",
        "crime_coefficient": 1.18,
        "violence_coefficient": 1.08,
        "theft_coefficient": 1.12,
        "traffic_coefficient": 1.02,
        "emergency_coefficient": 1.00,
        "source_note": "Profil județean Timiș",
    },
    {
        "county": "iasi",
        "city": "",
        "locality_type": "county",
        "crime_coefficient": 1.16,
        "violence_coefficient": 1.07,
        "theft_coefficient": 1.11,
        "traffic_coefficient": 1.01,
        "emergency_coefficient": 1.00,
        "source_note": "Profil județean Iași",
    },
    {
        "county": "constanta",
        "city": "",
        "locality_type": "county",
        "crime_coefficient": 1.22,
        "violence_coefficient": 1.10,
        "theft_coefficient": 1.18,
        "traffic_coefficient": 1.05,
        "emergency_coefficient": 1.00,
        "source_note": "Profil județean Constanța",
    },

    # ===== PROFILURI ORAȘE =====
    {
        "county": "arges",
        "city": "pitesti",
        "locality_type": "city",
        "crime_coefficient": 1.35,
        "violence_coefficient": 1.20,
        "theft_coefficient": 1.30,
        "traffic_coefficient": 1.05,
        "emergency_coefficient": 1.00,
        "source_note": "Profil oraș Pitești",
    },
    {
        "county": "arges",
        "city": "mioveni",
        "locality_type": "city",
        "crime_coefficient": 1.10,
        "violence_coefficient": 1.05,
        "theft_coefficient": 1.00,
        "traffic_coefficient": 1.00,
        "emergency_coefficient": 1.00,
        "source_note": "Profil oraș Mioveni",
    },
    {
        "county": "bucuresti",
        "city": "bucuresti",
        "locality_type": "city",
        "crime_coefficient": 1.45,
        "violence_coefficient": 1.30,
        "theft_coefficient": 1.40,
        "traffic_coefficient": 1.10,
        "emergency_coefficient": 1.00,
        "source_note": "Profil municipiu București",
    },
    {
        "county": "cluj",
        "city": "cluj-napoca",
        "locality_type": "city",
        "crime_coefficient": 1.20,
        "violence_coefficient": 1.10,
        "theft_coefficient": 1.15,
        "traffic_coefficient": 1.03,
        "emergency_coefficient": 1.00,
        "source_note": "Profil oraș Cluj-Napoca",
    },
    {
        "county": "timis",
        "city": "timisoara",
        "locality_type": "city",
        "crime_coefficient": 1.22,
        "violence_coefficient": 1.12,
        "theft_coefficient": 1.16,
        "traffic_coefficient": 1.04,
        "emergency_coefficient": 1.00,
        "source_note": "Profil oraș Timișoara",
    },
    {
        "county": "iasi",
        "city": "iasi",
        "locality_type": "city",
        "crime_coefficient": 1.19,
        "violence_coefficient": 1.10,
        "theft_coefficient": 1.14,
        "traffic_coefficient": 1.03,
        "emergency_coefficient": 1.00,
        "source_note": "Profil oraș Iași",
    },
    {
        "county": "constanta",
        "city": "constanta",
        "locality_type": "city",
        "crime_coefficient": 1.24,
        "violence_coefficient": 1.12,
        "theft_coefficient": 1.18,
        "traffic_coefficient": 1.05,
        "emergency_coefficient": 1.00,
        "source_note": "Profil oraș Constanța",
    },
]


INSERT_SQL = """
INSERT OR IGNORE INTO area_risk_profiles (
    county,
    city,
    locality_type,
    crime_coefficient,
    violence_coefficient,
    theft_coefficient,
    traffic_coefficient,
    emergency_coefficient,
    source_note
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
"""


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()

        rows = [
            (
                item["county"],
                item["city"],
                item["locality_type"],
                item["crime_coefficient"],
                item["violence_coefficient"],
                item["theft_coefficient"],
                item["traffic_coefficient"],
                item["emergency_coefficient"],
                item["source_note"],
            )
            for item in AREA_RISK_PROFILES
        ]

        cursor.executemany(INSERT_SQL, rows)
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM area_risk_profiles")
        total = cursor.fetchone()[0]

        print("area_risk_profiles seeded")
        print(f"total area profiles in db: {total}")
        print(f"db path: {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
