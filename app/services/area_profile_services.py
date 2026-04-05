import sqlite3
from pathlib import Path
from typing import Optional, Iterable

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "lazarus_safe.db"


def normalize_name(value: Optional[str]) -> str:
    if not value:
        return ""

    value = value.strip().lower()

    replacements = {
        "ă": "a",
        "â": "a",
        "î": "i",
        "ș": "s",
        "ş": "s",
        "ț": "t",
        "ţ": "t",
        "–": "-",
        "—": "-",
        "_": " ",
        "/": " ",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    value = " ".join(value.split())
    return value


COUNTY_PROFILES = [
    ("alba", None, "county", 0.95, 0.95, 0.95, 1.00, 1.00, "profil initial national"),
    ("arad", None, "county", 1.00, 1.00, 1.00, 1.05, 1.00, "profil initial national"),
    ("arges", None, "county", 1.10, 1.00, 1.15, 1.20, 1.00, "profil initial national"),
    ("bacau", None, "county", 1.00, 1.00, 1.00, 1.05, 1.00, "profil initial national"),
    ("bihor", None, "county", 1.00, 0.95, 1.00, 1.00, 1.00, "profil initial national"),
    ("bistrita-nasaud", None, "county", 0.90, 0.90, 0.90, 0.95, 0.95, "profil initial national"),
    ("botosani", None, "county", 0.95, 0.95, 0.95, 0.95, 1.00, "profil initial national"),
    ("braila", None, "county", 1.00, 1.00, 1.00, 1.00, 1.00, "profil initial national"),
    ("brasov", None, "county", 1.10, 1.00, 1.10, 1.10, 1.00, "profil initial national"),
    ("bucuresti", None, "county", 1.40, 1.20, 1.45, 1.35, 1.10, "profil initial national"),
    ("buzau", None, "county", 0.95, 0.95, 0.95, 1.00, 1.00, "profil initial national"),
    ("calarasi", None, "county", 0.95, 0.95, 0.95, 1.00, 1.00, "profil initial national"),
    ("caras-severin", None, "county", 0.90, 0.90, 0.90, 0.95, 0.95, "profil initial national"),
    ("cluj", None, "county", 1.15, 1.00, 1.15, 1.10, 1.00, "profil initial national"),
    ("constanta", None, "county", 1.20, 1.05, 1.20, 1.15, 1.05, "profil initial national"),
    ("covasna", None, "county", 0.90, 0.90, 0.90, 0.95, 0.95, "profil initial national"),
    ("dambovita", None, "county", 1.00, 1.00, 1.00, 1.05, 1.00, "profil initial national"),
    ("dolj", None, "county", 1.10, 1.05, 1.10, 1.10, 1.00, "profil initial national"),
    ("galati", None, "county", 1.05, 1.00, 1.05, 1.05, 1.00, "profil initial national"),
    ("giurgiu", None, "county", 0.95, 0.95, 0.95, 1.00, 1.00, "profil initial national"),
    ("gorj", None, "county", 0.95, 0.95, 0.95, 1.00, 0.95, "profil initial national"),
    ("harghita", None, "county", 0.90, 0.90, 0.90, 0.95, 0.95, "profil initial national"),
    ("hunedoara", None, "county", 1.00, 1.00, 1.00, 1.00, 1.00, "profil initial national"),
    ("ialomita", None, "county", 0.95, 0.95, 0.95, 1.00, 1.00, "profil initial national"),
    ("iasi", None, "county", 1.15, 1.05, 1.15, 1.10, 1.00, "profil initial national"),
    ("ilfov", None, "county", 1.15, 1.00, 1.15, 1.15, 1.00, "profil initial national"),
    ("maramures", None, "county", 0.95, 0.95, 0.95, 1.00, 0.95, "profil initial national"),
    ("mehedinti", None, "county", 0.95, 0.95, 0.95, 1.00, 1.00, "profil initial national"),
    ("mures", None, "county", 1.00, 1.00, 1.00, 1.00, 1.00, "profil initial national"),
    ("neamt", None, "county", 0.95, 0.95, 0.95, 1.00, 1.00, "profil initial national"),
    ("olt", None, "county", 0.95, 0.95, 0.95, 1.00, 1.00, "profil initial national"),
    ("prahova", None, "county", 1.10, 1.00, 1.10, 1.10, 1.00, "profil initial national"),
    ("satu-mare", None, "county", 0.95, 0.95, 0.95, 1.00, 0.95, "profil initial national"),
    ("salaj", None, "county", 0.90, 0.90, 0.90, 0.95, 0.95, "profil initial national"),
    ("sibiu", None, "county", 1.00, 0.95, 1.00, 1.00, 1.00, "profil initial national"),
    ("suceava", None, "county", 1.00, 1.00, 1.00, 1.05, 1.00, "profil initial national"),
    ("teleorman", None, "county", 0.95, 0.95, 0.95, 1.00, 1.00, "profil initial national"),
    ("timis", None, "county", 1.20, 1.05, 1.20, 1.10, 1.00, "profil initial national"),
    ("tulcea", None, "county", 0.90, 0.90, 0.90, 0.95, 1.00, "profil initial national"),
    ("vaslui", None, "county", 0.95, 0.95, 0.95, 1.00, 1.00, "profil initial national"),
    ("valcea", None, "county", 0.95, 0.95, 0.95, 1.00, 0.95, "profil initial national"),
    ("vrancea", None, "county", 0.95, 0.95, 0.95, 1.00, 1.00, "profil initial national"),
]

CITY_PROFILES = [
    ("bucuresti", "bucuresti", "city", 1.55, 1.30, 1.60, 1.40, 1.10, "profil initial municipiu capitala"),
    ("cluj", "cluj-napoca", "city", 1.25, 1.05, 1.30, 1.15, 1.00, "profil initial municipiu mare"),
    ("timis", "timisoara", "city", 1.30, 1.10, 1.30, 1.15, 1.00, "profil initial municipiu mare"),
    ("iasi", "iasi", "city", 1.25, 1.10, 1.25, 1.15, 1.00, "profil initial municipiu mare"),
    ("constanta", "constanta", "city", 1.30, 1.10, 1.30, 1.20, 1.05, "profil initial municipiu mare"),
    ("brasov", "brasov", "city", 1.20, 1.00, 1.20, 1.10, 1.00, "profil initial municipiu mare"),
    ("dolj", "craiova", "city", 1.20, 1.10, 1.20, 1.15, 1.00, "profil initial municipiu mare"),
    ("galati", "galati", "city", 1.15, 1.05, 1.15, 1.10, 1.00, "profil initial municipiu mare"),
    ("prahova", "ploiesti", "city", 1.20, 1.05, 1.20, 1.15, 1.00, "profil initial municipiu mare"),
    ("arges", "pitesti", "city", 1.20, 1.05, 1.25, 1.15, 1.00, "profil initial municipiu mare"),
    ("arges", "mioveni", "city", 1.00, 0.95, 1.00, 1.05, 1.00, "profil initial municipiu industrial"),
    ("sibiu", "sibiu", "city", 1.10, 1.00, 1.10, 1.05, 1.00, "profil initial municipiu"),
    ("mures", "targu mures", "city", 1.10, 1.00, 1.10, 1.05, 1.00, "profil initial municipiu"),
    ("bihor", "oradea", "city", 1.10, 1.00, 1.10, 1.05, 1.00, "profil initial municipiu"),
    ("arad", "arad", "city", 1.10, 1.00, 1.10, 1.05, 1.00, "profil initial municipiu"),
    ("bacau", "bacau", "city", 1.10, 1.00, 1.10, 1.05, 1.00, "profil initial municipiu"),
    ("suceava", "suceava", "city", 1.05, 1.00, 1.05, 1.05, 1.00, "profil initial municipiu"),
    ("neamt", "piatra neamt", "city", 1.05, 1.00, 1.05, 1.05, 1.00, "profil initial municipiu"),
    ("alba", "alba iulia", "city", 1.00, 0.95, 1.00, 1.00, 1.00, "profil initial resedinta"),
    ("bistrita-nasaud", "bistrita", "city", 0.95, 0.95, 0.95, 1.00, 0.95, "profil initial resedinta"),
    ("botosani", "botosani", "city", 1.00, 0.95, 1.00, 1.00, 1.00, "profil initial resedinta"),
    ("braila", "braila", "city", 1.10, 1.00, 1.10, 1.05, 1.00, "profil initial resedinta"),
    ("buzau", "buzau", "city", 1.05, 1.00, 1.05, 1.05, 1.00, "profil initial resedinta"),
    ("calarasi", "calarasi", "city", 1.00, 0.95, 1.00, 1.00, 1.00, "profil initial resedinta"),
    ("caras-severin", "resita", "city", 0.95, 0.95, 0.95, 1.00, 0.95, "profil initial resedinta"),
    ("covasna", "sfantu gheorghe", "city", 0.95, 0.95, 0.95, 1.00, 0.95, "profil initial resedinta"),
    ("dambovita", "targoviste", "city", 1.05, 1.00, 1.05, 1.05, 1.00, "profil initial resedinta"),
    ("giurgiu", "giurgiu", "city", 1.00, 0.95, 1.00, 1.00, 1.00, "profil initial resedinta"),
    ("gorj", "targu jiu", "city", 1.00, 0.95, 1.00, 1.00, 0.95, "profil initial resedinta"),
    ("harghita", "miercurea ciuc", "city", 0.95, 0.95, 0.95, 1.00, 0.95, "profil initial resedinta"),
    ("hunedoara", "deva", "city", 1.00, 1.00, 1.00, 1.00, 1.00, "profil initial resedinta"),
    ("ialomita", "slobozia", "city", 1.00, 0.95, 1.00, 1.00, 1.00, "profil initial resedinta"),
    ("ilfov", "buftea", "city", 1.05, 1.00, 1.05, 1.05, 1.00, "profil initial resedinta"),
    ("maramures", "baia mare", "city", 1.05, 1.00, 1.05, 1.05, 0.95, "profil initial resedinta"),
    ("mehedinti", "drobeta-turnu severin", "city", 1.00, 0.95, 1.00, 1.00, 1.00, "profil initial resedinta"),
    ("olt", "slatina", "city", 1.00, 0.95, 1.00, 1.00, 1.00, "profil initial resedinta"),
    ("satu-mare", "satu mare", "city", 1.00, 0.95, 1.00, 1.00, 0.95, "profil initial resedinta"),
    ("salaj", "zalau", "city", 0.95, 0.95, 0.95, 1.00, 0.95, "profil initial resedinta"),
    ("teleorman", "alexandria", "city", 1.00, 0.95, 1.00, 1.00, 1.00, "profil initial resedinta"),
    ("tulcea", "tulcea", "city", 0.95, 0.95, 0.95, 1.00, 1.00, "profil initial resedinta"),
    ("vaslui", "vaslui", "city", 1.00, 0.95, 1.00, 1.00, 1.00, "profil initial resedinta"),
    ("valcea", "ramnicu valcea", "city", 1.00, 0.95, 1.00, 1.00, 0.95, "profil initial resedinta"),
    ("vrancea", "focsani", "city", 1.00, 0.95, 1.00, 1.00, 1.00, "profil initial resedinta"),
    ("hunedoara", "hunedoara", "city", 1.00, 1.00, 1.00, 1.00, 1.00, "profil initial municipiu secundar"),
    ("hunedoara", "petrosani", "city", 1.00, 1.00, 1.00, 1.00, 1.00, "profil initial municipiu secundar"),
    ("maramures", "sighetu marmatiei", "city", 0.95, 0.95, 0.95, 1.00, 0.95, "profil initial municipiu secundar"),
    ("sibiu", "medias", "city", 1.00, 0.95, 1.00, 1.00, 1.00, "profil initial municipiu secundar"),
    ("mures", "sighisoara", "city", 1.00, 0.95, 1.00, 1.00, 1.00, "profil initial municipiu secundar"),
    ("constanta", "mangalia", "city", 1.10, 1.00, 1.10, 1.10, 1.00, "profil initial municipiu secundar"),
    ("constanta", "medgidia", "city", 1.05, 1.00, 1.05, 1.05, 1.00, "profil initial municipiu secundar"),
    ("cluj", "turda", "city", 1.05, 1.00, 1.05, 1.00, 1.00, "profil initial municipiu secundar"),
    ("cluj", "dej", "city", 1.00, 0.95, 1.00, 1.00, 1.00, "profil initial municipiu secundar"),
    ("bacau", "onesti", "city", 1.00, 0.95, 1.00, 1.00, 1.00, "profil initial municipiu secundar"),
    ("dolj", "bailesti", "city", 1.00, 0.95, 1.00, 1.00, 1.00, "profil initial municipiu secundar"),
    ("arges", "campulung", "city", 1.00, 0.95, 1.00, 1.00, 1.00, "profil initial municipiu secundar"),
    ("arges", "curtea de arges", "city", 1.00, 0.95, 1.00, 1.00, 1.00, "profil initial municipiu secundar"),
    ("prahova", "campina", "city", 1.05, 1.00, 1.05, 1.05, 1.00, "profil initial municipiu secundar"),
    ("bihor", "salonta", "city", 1.00, 0.95, 1.00, 1.00, 1.00, "profil initial municipiu secundar"),
    ("arad", "lipova", "city", 0.95, 0.95, 0.95, 1.00, 1.00, "profil initial municipiu secundar"),
    ("suceava", "radauti", "city", 1.00, 1.00, 1.00, 1.05, 1.00, "profil initial municipiu secundar"),
    ("suceava", "falticeni", "city", 1.00, 0.95, 1.00, 1.00, 1.00, "profil initial municipiu secundar"),
    ("neamt", "roman", "city", 1.00, 0.95, 1.00, 1.00, 1.00, "profil initial municipiu secundar"),
]

def upsert_profile(cursor, row):
    county, city, locality_type, crime_c, violence_c, theft_c, traffic_c, emergency_c, source_note = row
    county = normalize_name(county)
    city = normalize_name(city)

    cursor.execute("""
        INSERT INTO area_risk_profiles (
            county,
            city,
            locality_type,
            crime_coefficient,
            violence_coefficient,
            theft_coefficient,
            traffic_coefficient,
            emergency_coefficient,
            source_note,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(county, city) DO UPDATE SET
            locality_type = excluded.locality_type,
            crime_coefficient = excluded.crime_coefficient,
            violence_coefficient = excluded.violence_coefficient,
            theft_coefficient = excluded.theft_coefficient,
            traffic_coefficient = excluded.traffic_coefficient,
            emergency_coefficient = excluded.emergency_coefficient,
            source_note = excluded.source_note,
            updated_at = CURRENT_TIMESTAMP
    """, (
        county,
        city,
        locality_type,
        crime_c,
        violence_c,
        theft_c,
        traffic_c,
        emergency_c,
        source_note
    ))


def seed_profiles(cursor, profiles: Iterable[tuple]):
    for row in profiles:
        upsert_profile(cursor, row)


def validate_profiles():
    all_rows = COUNTY_PROFILES + CITY_PROFILES
    seen = set()
    duplicates = []

    for row in all_rows:
        county = normalize_name(row[0])
        city = normalize_name(row[1])
        key = (county, city)

        if key in seen:
            duplicates.append(key)
        seen.add(key)

    if duplicates:
        unique_dups = sorted(set(duplicates))
        dup_text = ", ".join([f"{county}/{city or '[county]'}" for county, city in unique_dups])
        raise ValueError(f"Duplicate area profiles found: {dup_text}")


def main():
    validate_profiles()

    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        seed_profiles(cursor, COUNTY_PROFILES)
        seed_profiles(cursor, CITY_PROFILES)
        conn.commit()
    finally:
        conn.close()

    total = len(COUNTY_PROFILES) + len(CITY_PROFILES)
    print(f"Area risk profiles upserted successfully! Total profiles processed: {total}")


if __name__ == "__main__":
    main()