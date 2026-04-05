from app.db import get_connection, get_db_path


AREA_RISK_PROFILES = [
    # București
    {
        "county": "bucuresti",
        "city": "",
        "locality_type": "county",
        "crime_coefficient": 1.40,
        "violence_coefficient": 1.25,
        "theft_coefficient": 1.35,
        "traffic_coefficient": 1.10,
        "emergency_coefficient": 1.00,
        "source_note": "Profil judetean/municipal Bucuresti",
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
        "source_note": "Profil municipiu Bucuresti",
    },

    # Județe - acoperire națională
    {"county": "alba", "city": "", "locality_type": "county", "crime_coefficient": 1.05, "violence_coefficient": 1.00, "theft_coefficient": 1.02, "traffic_coefficient": 1.00, "emergency_coefficient": 1.00, "source_note": "Profil judetean Alba"},
    {"county": "arad", "city": "", "locality_type": "county", "crime_coefficient": 1.08, "violence_coefficient": 1.02, "theft_coefficient": 1.05, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil judetean Arad"},
    {"county": "arges", "city": "", "locality_type": "county", "crime_coefficient": 1.20, "violence_coefficient": 1.10, "theft_coefficient": 1.15, "traffic_coefficient": 1.00, "emergency_coefficient": 1.00, "source_note": "Profil judetean Arges"},
    {"county": "bacau", "city": "", "locality_type": "county", "crime_coefficient": 1.12, "violence_coefficient": 1.06, "theft_coefficient": 1.08, "traffic_coefficient": 1.02, "emergency_coefficient": 1.00, "source_note": "Profil judetean Bacau"},
    {"county": "bihor", "city": "", "locality_type": "county", "crime_coefficient": 1.10, "violence_coefficient": 1.04, "theft_coefficient": 1.08, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil judetean Bihor"},
    {"county": "bistrita nasaud", "city": "", "locality_type": "county", "crime_coefficient": 1.03, "violence_coefficient": 1.00, "theft_coefficient": 1.02, "traffic_coefficient": 1.00, "emergency_coefficient": 1.00, "source_note": "Profil judetean Bistrita-Nasaud"},
    {"county": "botosani", "city": "", "locality_type": "county", "crime_coefficient": 1.05, "violence_coefficient": 1.01, "theft_coefficient": 1.03, "traffic_coefficient": 1.00, "emergency_coefficient": 1.00, "source_note": "Profil judetean Botosani"},
    {"county": "braila", "city": "", "locality_type": "county", "crime_coefficient": 1.09, "violence_coefficient": 1.04, "theft_coefficient": 1.06, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil judetean Braila"},
    {"county": "brasov", "city": "", "locality_type": "county", "crime_coefficient": 1.13, "violence_coefficient": 1.06, "theft_coefficient": 1.10, "traffic_coefficient": 1.02, "emergency_coefficient": 1.00, "source_note": "Profil judetean Brasov"},
    {"county": "buzau", "city": "", "locality_type": "county", "crime_coefficient": 1.08, "violence_coefficient": 1.03, "theft_coefficient": 1.05, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil judetean Buzau"},
    {"county": "calarasi", "city": "", "locality_type": "county", "crime_coefficient": 1.07, "violence_coefficient": 1.03, "theft_coefficient": 1.04, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil judetean Calarasi"},
    {"county": "caras severin", "city": "", "locality_type": "county", "crime_coefficient": 1.04, "violence_coefficient": 1.00, "theft_coefficient": 1.02, "traffic_coefficient": 1.00, "emergency_coefficient": 1.00, "source_note": "Profil judetean Caras-Severin"},
    {"county": "cluj", "city": "", "locality_type": "county", "crime_coefficient": 1.15, "violence_coefficient": 1.05, "theft_coefficient": 1.10, "traffic_coefficient": 1.00, "emergency_coefficient": 1.00, "source_note": "Profil judetean Cluj"},
    {"county": "constanta", "city": "", "locality_type": "county", "crime_coefficient": 1.22, "violence_coefficient": 1.10, "theft_coefficient": 1.18, "traffic_coefficient": 1.05, "emergency_coefficient": 1.00, "source_note": "Profil judetean Constanta"},
    {"county": "covasna", "city": "", "locality_type": "county", "crime_coefficient": 1.02, "violence_coefficient": 1.00, "theft_coefficient": 1.01, "traffic_coefficient": 1.00, "emergency_coefficient": 1.00, "source_note": "Profil judetean Covasna"},
    {"county": "dambovita", "city": "", "locality_type": "county", "crime_coefficient": 1.10, "violence_coefficient": 1.04, "theft_coefficient": 1.07, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil judetean Dambovita"},
    {"county": "dolj", "city": "", "locality_type": "county", "crime_coefficient": 1.14, "violence_coefficient": 1.07, "theft_coefficient": 1.10, "traffic_coefficient": 1.02, "emergency_coefficient": 1.00, "source_note": "Profil judetean Dolj"},
    {"county": "galati", "city": "", "locality_type": "county", "crime_coefficient": 1.12, "violence_coefficient": 1.06, "theft_coefficient": 1.08, "traffic_coefficient": 1.02, "emergency_coefficient": 1.00, "source_note": "Profil judetean Galati"},
    {"county": "giurgiu", "city": "", "locality_type": "county", "crime_coefficient": 1.09, "violence_coefficient": 1.04, "theft_coefficient": 1.06, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil judetean Giurgiu"},
    {"county": "gorj", "city": "", "locality_type": "county", "crime_coefficient": 1.06, "violence_coefficient": 1.02, "theft_coefficient": 1.04, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil judetean Gorj"},
    {"county": "harghita", "city": "", "locality_type": "county", "crime_coefficient": 1.02, "violence_coefficient": 1.00, "theft_coefficient": 1.01, "traffic_coefficient": 1.00, "emergency_coefficient": 1.00, "source_note": "Profil judetean Harghita"},
    {"county": "hunedoara", "city": "", "locality_type": "county", "crime_coefficient": 1.08, "violence_coefficient": 1.03, "theft_coefficient": 1.05, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil judetean Hunedoara"},
    {"county": "ialomita", "city": "", "locality_type": "county", "crime_coefficient": 1.07, "violence_coefficient": 1.03, "theft_coefficient": 1.04, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil judetean Ialomita"},
    {"county": "iasi", "city": "", "locality_type": "county", "crime_coefficient": 1.16, "violence_coefficient": 1.07, "theft_coefficient": 1.11, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil judetean Iasi"},
    {"county": "ilfov", "city": "", "locality_type": "county", "crime_coefficient": 1.18, "violence_coefficient": 1.08, "theft_coefficient": 1.12, "traffic_coefficient": 1.03, "emergency_coefficient": 1.00, "source_note": "Profil judetean Ilfov"},
    {"county": "maramures", "city": "", "locality_type": "county", "crime_coefficient": 1.06, "violence_coefficient": 1.02, "theft_coefficient": 1.04, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil judetean Maramures"},
    {"county": "mehedinti", "city": "", "locality_type": "county", "crime_coefficient": 1.05, "violence_coefficient": 1.01, "theft_coefficient": 1.03, "traffic_coefficient": 1.00, "emergency_coefficient": 1.00, "source_note": "Profil judetean Mehedinti"},
    {"county": "mures", "city": "", "locality_type": "county", "crime_coefficient": 1.08, "violence_coefficient": 1.03, "theft_coefficient": 1.05, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil judetean Mures"},
    {"county": "neamt", "city": "", "locality_type": "county", "crime_coefficient": 1.07, "violence_coefficient": 1.02, "theft_coefficient": 1.05, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil judetean Neamt"},
    {"county": "olt", "city": "", "locality_type": "county", "crime_coefficient": 1.09, "violence_coefficient": 1.04, "theft_coefficient": 1.06, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil judetean Olt"},
    {"county": "prahova", "city": "", "locality_type": "county", "crime_coefficient": 1.14, "violence_coefficient": 1.07, "theft_coefficient": 1.10, "traffic_coefficient": 1.03, "emergency_coefficient": 1.00, "source_note": "Profil judetean Prahova"},
    {"county": "salaj", "city": "", "locality_type": "county", "crime_coefficient": 1.03, "violence_coefficient": 1.00, "theft_coefficient": 1.02, "traffic_coefficient": 1.00, "emergency_coefficient": 1.00, "source_note": "Profil judetean Salaj"},
    {"county": "satu mare", "city": "", "locality_type": "county", "crime_coefficient": 1.05, "violence_coefficient": 1.01, "theft_coefficient": 1.03, "traffic_coefficient": 1.00, "emergency_coefficient": 1.00, "source_note": "Profil judetean Satu Mare"},
    {"county": "sibiu", "city": "", "locality_type": "county", "crime_coefficient": 1.09, "violence_coefficient": 1.03, "theft_coefficient": 1.06, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil judetean Sibiu"},
    {"county": "suceava", "city": "", "locality_type": "county", "crime_coefficient": 1.08, "violence_coefficient": 1.03, "theft_coefficient": 1.05, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil judetean Suceava"},
    {"county": "teleorman", "city": "", "locality_type": "county", "crime_coefficient": 1.10, "violence_coefficient": 1.05, "theft_coefficient": 1.07, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil judetean Teleorman"},
    {"county": "timis", "city": "", "locality_type": "county", "crime_coefficient": 1.18, "violence_coefficient": 1.08, "theft_coefficient": 1.12, "traffic_coefficient": 1.02, "emergency_coefficient": 1.00, "source_note": "Profil judetean Timis"},
    {"county": "tulcea", "city": "", "locality_type": "county", "crime_coefficient": 1.04, "violence_coefficient": 1.01, "theft_coefficient": 1.02, "traffic_coefficient": 1.00, "emergency_coefficient": 1.00, "source_note": "Profil judetean Tulcea"},
    {"county": "valcea", "city": "", "locality_type": "county", "crime_coefficient": 1.07, "violence_coefficient": 1.02, "theft_coefficient": 1.05, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil judetean Valcea"},
    {"county": "vaslui", "city": "", "locality_type": "county", "crime_coefficient": 1.08, "violence_coefficient": 1.03, "theft_coefficient": 1.05, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil judetean Vaslui"},
    {"county": "vrancea", "city": "", "locality_type": "county", "crime_coefficient": 1.07, "violence_coefficient": 1.02, "theft_coefficient": 1.05, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil judetean Vrancea"},

    # Orașe mari / reședințe relevante
    {"county": "alba", "city": "alba iulia", "locality_type": "city", "crime_coefficient": 1.08, "violence_coefficient": 1.02, "theft_coefficient": 1.05, "traffic_coefficient": 1.00, "emergency_coefficient": 1.00, "source_note": "Profil oras Alba Iulia"},
    {"county": "arad", "city": "arad", "locality_type": "city", "crime_coefficient": 1.12, "violence_coefficient": 1.05, "theft_coefficient": 1.08, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil oras Arad"},
    {"county": "arges", "city": "pitesti", "locality_type": "city", "crime_coefficient": 1.35, "violence_coefficient": 1.20, "theft_coefficient": 1.30, "traffic_coefficient": 1.05, "emergency_coefficient": 1.00, "source_note": "Profil oras Pitesti"},
    {"county": "arges", "city": "mioveni", "locality_type": "city", "crime_coefficient": 1.10, "violence_coefficient": 1.05, "theft_coefficient": 1.00, "traffic_coefficient": 1.00, "emergency_coefficient": 1.00, "source_note": "Profil oras Mioveni"},
    {"county": "bacau", "city": "bacau", "locality_type": "city", "crime_coefficient": 1.15, "violence_coefficient": 1.08, "theft_coefficient": 1.10, "traffic_coefficient": 1.02, "emergency_coefficient": 1.00, "source_note": "Profil oras Bacau"},
    {"county": "bihor", "city": "oradea", "locality_type": "city", "crime_coefficient": 1.13, "violence_coefficient": 1.06, "theft_coefficient": 1.09, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil oras Oradea"},
    {"county": "bistrita nasaud", "city": "bistrita", "locality_type": "city", "crime_coefficient": 1.05, "violence_coefficient": 1.01, "theft_coefficient": 1.03, "traffic_coefficient": 1.00, "emergency_coefficient": 1.00, "source_note": "Profil oras Bistrita"},
    {"county": "botosani", "city": "botosani", "locality_type": "city", "crime_coefficient": 1.07, "violence_coefficient": 1.02, "theft_coefficient": 1.04, "traffic_coefficient": 1.00, "emergency_coefficient": 1.00, "source_note": "Profil oras Botosani"},
    {"county": "braila", "city": "braila", "locality_type": "city", "crime_coefficient": 1.12, "violence_coefficient": 1.05, "theft_coefficient": 1.08, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil oras Braila"},
    {"county": "brasov", "city": "brasov", "locality_type": "city", "crime_coefficient": 1.16, "violence_coefficient": 1.08, "theft_coefficient": 1.12, "traffic_coefficient": 1.02, "emergency_coefficient": 1.00, "source_note": "Profil oras Brasov"},
    {"county": "buzau", "city": "buzau", "locality_type": "city", "crime_coefficient": 1.10, "violence_coefficient": 1.04, "theft_coefficient": 1.06, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil oras Buzau"},
    {"county": "calarasi", "city": "calarasi", "locality_type": "city", "crime_coefficient": 1.09, "violence_coefficient": 1.04, "theft_coefficient": 1.05, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil oras Calarasi"},
    {"county": "caras severin", "city": "resita", "locality_type": "city", "crime_coefficient": 1.05, "violence_coefficient": 1.01, "theft_coefficient": 1.03, "traffic_coefficient": 1.00, "emergency_coefficient": 1.00, "source_note": "Profil oras Resita"},
    {"county": "cluj", "city": "cluj-napoca", "locality_type": "city", "crime_coefficient": 1.20, "violence_coefficient": 1.10, "theft_coefficient": 1.15, "traffic_coefficient": 1.03, "emergency_coefficient": 1.00, "source_note": "Profil oras Cluj-Napoca"},
    {"county": "constanta", "city": "constanta", "locality_type": "city", "crime_coefficient": 1.24, "violence_coefficient": 1.12, "theft_coefficient": 1.18, "traffic_coefficient": 1.05, "emergency_coefficient": 1.00, "source_note": "Profil oras Constanta"},
    {"county": "covasna", "city": "sfantu gheorghe", "locality_type": "city", "crime_coefficient": 1.03, "violence_coefficient": 1.00, "theft_coefficient": 1.02, "traffic_coefficient": 1.00, "emergency_coefficient": 1.00, "source_note": "Profil oras Sfantu Gheorghe"},
    {"county": "dambovita", "city": "targoviste", "locality_type": "city", "crime_coefficient": 1.12, "violence_coefficient": 1.05, "theft_coefficient": 1.08, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil oras Targoviste"},
    {"county": "dolj", "city": "craiova", "locality_type": "city", "crime_coefficient": 1.18, "violence_coefficient": 1.10, "theft_coefficient": 1.14, "traffic_coefficient": 1.03, "emergency_coefficient": 1.00, "source_note": "Profil oras Craiova"},
    {"county": "galati", "city": "galati", "locality_type": "city", "crime_coefficient": 1.16, "violence_coefficient": 1.08, "theft_coefficient": 1.12, "traffic_coefficient": 1.02, "emergency_coefficient": 1.00, "source_note": "Profil oras Galati"},
    {"county": "giurgiu", "city": "giurgiu", "locality_type": "city", "crime_coefficient": 1.11, "violence_coefficient": 1.05, "theft_coefficient": 1.07, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil oras Giurgiu"},
    {"county": "gorj", "city": "targu jiu", "locality_type": "city", "crime_coefficient": 1.08, "violence_coefficient": 1.03, "theft_coefficient": 1.05, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil oras Targu Jiu"},
    {"county": "harghita", "city": "miercurea ciuc", "locality_type": "city", "crime_coefficient": 1.03, "violence_coefficient": 1.00, "theft_coefficient": 1.02, "traffic_coefficient": 1.00, "emergency_coefficient": 1.00, "source_note": "Profil oras Miercurea Ciuc"},
    {"county": "hunedoara", "city": "deva", "locality_type": "city", "crime_coefficient": 1.10, "violence_coefficient": 1.04, "theft_coefficient": 1.06, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil oras Deva"},
    {"county": "ialomita", "city": "slobozia", "locality_type": "city", "crime_coefficient": 1.09, "violence_coefficient": 1.04, "theft_coefficient": 1.05, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil oras Slobozia"},
    {"county": "iasi", "city": "iasi", "locality_type": "city", "crime_coefficient": 1.19, "violence_coefficient": 1.10, "theft_coefficient": 1.14, "traffic_coefficient": 1.03, "emergency_coefficient": 1.00, "source_note": "Profil oras Iasi"},
    {"county": "ilfov", "city": "voluntari", "locality_type": "city", "crime_coefficient": 1.20, "violence_coefficient": 1.10, "theft_coefficient": 1.14, "traffic_coefficient": 1.04, "emergency_coefficient": 1.00, "source_note": "Profil oras Voluntari"},
    {"county": "maramures", "city": "baia mare", "locality_type": "city", "crime_coefficient": 1.08, "violence_coefficient": 1.03, "theft_coefficient": 1.05, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil oras Baia Mare"},
    {"county": "mehedinti", "city": "drobeta turnu severin", "locality_type": "city", "crime_coefficient": 1.07, "violence_coefficient": 1.02, "theft_coefficient": 1.04, "traffic_coefficient": 1.00, "emergency_coefficient": 1.00, "source_note": "Profil oras Drobeta-Turnu Severin"},
    {"county": "mures", "city": "targu mures", "locality_type": "city", "crime_coefficient": 1.10, "violence_coefficient": 1.04, "theft_coefficient": 1.06, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil oras Targu Mures"},
    {"county": "neamt", "city": "piatra neamt", "locality_type": "city", "crime_coefficient": 1.09, "violence_coefficient": 1.03, "theft_coefficient": 1.06, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil oras Piatra Neamt"},
    {"county": "olt", "city": "slatina", "locality_type": "city", "crime_coefficient": 1.11, "violence_coefficient": 1.05, "theft_coefficient": 1.07, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil oras Slatina"},
    {"county": "prahova", "city": "ploiesti", "locality_type": "city", "crime_coefficient": 1.18, "violence_coefficient": 1.10, "theft_coefficient": 1.13, "traffic_coefficient": 1.03, "emergency_coefficient": 1.00, "source_note": "Profil oras Ploiesti"},
    {"county": "salaj", "city": "zalau", "locality_type": "city", "crime_coefficient": 1.05, "violence_coefficient": 1.01, "theft_coefficient": 1.03, "traffic_coefficient": 1.00, "emergency_coefficient": 1.00, "source_note": "Profil oras Zalau"},
    {"county": "satu mare", "city": "satu mare", "locality_type": "city", "crime_coefficient": 1.07, "violence_coefficient": 1.02, "theft_coefficient": 1.04, "traffic_coefficient": 1.00, "emergency_coefficient": 1.00, "source_note": "Profil oras Satu Mare"},
    {"county": "sibiu", "city": "sibiu", "locality_type": "city", "crime_coefficient": 1.12, "violence_coefficient": 1.05, "theft_coefficient": 1.08, "traffic_coefficient": 1.02, "emergency_coefficient": 1.00, "source_note": "Profil oras Sibiu"},
    {"county": "suceava", "city": "suceava", "locality_type": "city", "crime_coefficient": 1.10, "violence_coefficient": 1.04, "theft_coefficient": 1.06, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil oras Suceava"},
    {"county": "teleorman", "city": "alexandria", "locality_type": "city", "crime_coefficient": 1.12, "violence_coefficient": 1.06, "theft_coefficient": 1.08, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil oras Alexandria"},
    {"county": "timis", "city": "timisoara", "locality_type": "city", "crime_coefficient": 1.22, "violence_coefficient": 1.12, "theft_coefficient": 1.16, "traffic_coefficient": 1.04, "emergency_coefficient": 1.00, "source_note": "Profil oras Timisoara"},
    {"county": "tulcea", "city": "tulcea", "locality_type": "city", "crime_coefficient": 1.06, "violence_coefficient": 1.02, "theft_coefficient": 1.03, "traffic_coefficient": 1.00, "emergency_coefficient": 1.00, "source_note": "Profil oras Tulcea"},
    {"county": "valcea", "city": "ramnicu valcea", "locality_type": "city", "crime_coefficient": 1.09, "violence_coefficient": 1.03, "theft_coefficient": 1.06, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil oras Ramnicu Valcea"},
    {"county": "vaslui", "city": "vaslui", "locality_type": "city", "crime_coefficient": 1.10, "violence_coefficient": 1.04, "theft_coefficient": 1.06, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil oras Vaslui"},
    {"county": "vrancea", "city": "focsani", "locality_type": "city", "crime_coefficient": 1.09, "violence_coefficient": 1.03, "theft_coefficient": 1.06, "traffic_coefficient": 1.01, "emergency_coefficient": 1.00, "source_note": "Profil oras Focsani"},
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
    conn = get_connection()
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

        cursor.execute("SELECT COUNT(*) AS total FROM area_risk_profiles")
        total = cursor.fetchone()["total"]

        print("area_risk_profiles seeded")
        print(f"total area profiles in db: {total}")
        print(f"db path: {get_db_path()}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()