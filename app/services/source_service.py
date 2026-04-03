from typing import Optional
from app.db import get_connection


def normalize_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    value = value.lower().strip()
    replacements = {
        "ă": "a",
        "â": "a",
        "î": "i",
        "ș": "s",
        "ş": "s",
        "ț": "t",
        "ţ": "t",
    }

    for old, new in replacements.items():
        value = value.replace(old, new)

    value = value.replace("județul ", "").replace("judetul ", "")
    value = value.replace("municipiul ", "").replace("orasul ", "").replace("orașul ", "")
    return value.strip()


def get_sources_used(county: Optional[str] = None, city: Optional[str] = None) -> list[str]:
    conn = get_connection()
    cursor = conn.cursor()

    county_n = normalize_text(county) if county else None
    city_n = normalize_text(city) if city else None

    if county_n and city_n:
        cursor.execute("""
            SELECT DISTINCT name
            FROM sources
            WHERE is_active = 1
              AND (
                    (county = ? AND city = ?)
                    OR (county = ? AND city IS NULL)
                    OR (county IS NULL AND city IS NULL)
                  )
            ORDER BY trust_level DESC, id ASC
        """, (county_n, city_n, county_n))

    elif county_n:
        cursor.execute("""
            SELECT DISTINCT name
            FROM sources
            WHERE is_active = 1
              AND (
                    county = ?
                    OR county IS NULL
                  )
            ORDER BY trust_level DESC, id ASC
        """, (county_n,))

    else:
        cursor.execute("""
            SELECT DISTINCT name
            FROM sources
            WHERE is_active = 1
            ORDER BY trust_level DESC, id ASC
        """)

    rows = cursor.fetchall()
    conn.close()

    return [row["name"] for row in rows]


def get_source_records(county: Optional[str] = None, city: Optional[str] = None) -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()

    county_n = normalize_text(county) if county else None
    city_n = normalize_text(city) if city else None

    if county_n and city_n:
        cursor.execute("""
            SELECT id, name, source_type, base_url, county, city, trust_level, is_active
            FROM sources
            WHERE is_active = 1
              AND (
                    (county = ? AND city = ?)
                    OR (county = ? AND city IS NULL)
                    OR (county IS NULL AND city IS NULL)
                  )
            ORDER BY trust_level DESC, id ASC
        """, (county_n, city_n, county_n))

    elif county_n:
        cursor.execute("""
            SELECT id, name, source_type, base_url, county, city, trust_level, is_active
            FROM sources
            WHERE is_active = 1
              AND (
                    county = ?
                    OR county IS NULL
                  )
            ORDER BY trust_level DESC, id ASC
        """, (county_n,))

    else:
        cursor.execute("""
            SELECT id, name, source_type, base_url, county, city, trust_level, is_active
            FROM sources
            WHERE is_active = 1
            ORDER BY trust_level DESC, id ASC
        """)

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row["id"],
            "name": row["name"],
            "source_type": row["source_type"],
            "base_url": row["base_url"],
            "county": row["county"],
            "city": row["city"],
            "trust_level": row["trust_level"],
            "is_active": row["is_active"],
        }
        for row in rows
    ]


def insert_source(
    name: str,
    source_type: str,
    base_url: str,
    county: Optional[str] = None,
    city: Optional[str] = None,
    trust_level: int = 3,
    is_active: int = 1
) -> int:
    conn = get_connection()
    cursor = conn.cursor()

    county_n = normalize_text(county) if county else None
    city_n = normalize_text(city) if city else None

    cursor.execute("""
        INSERT INTO sources (
            name,
            source_type,
            base_url,
            county,
            city,
            trust_level,
            is_active
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        name.strip(),
        source_type.strip().lower(),
        base_url.strip(),
        county_n,
        city_n,
        trust_level,
        is_active
    ))

    conn.commit()
    source_id = cursor.lastrowid
    conn.close()
    return source_id


def deactivate_source(source_id: int) -> None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE sources
        SET is_active = 0
        WHERE id = ?
    """, (source_id,))

    conn.commit()
    conn.close()