rom __future__ import annotations

from typing import Optional, Any
from app.db import get_connection

DEFAULT_LOOKBACK_DAYS = 60

INCIDENT_KEYS = (
    "homicide",
    "sexual_violence",
    "robbery",
    "theft",
    "violence",
    "traffic",
    "emergency",
    "public_order",
    "general",
)

SEVERITY_MULTIPLIERS = {
    "critical": 2.2,
    "high": 1.6,
    "medium": 1.0,
    "low": 0.6,
}

BASE_WEIGHTS = {
    "homicide": 8.0,
    "sexual_violence": 6.0,
    "robbery": 4.5,
    "violence": 3.0,
    "theft": 1.8,
    "traffic": 1.3,
    "emergency": 1.5,
    "public_order": 0.9,
    "general": 0.4,
}


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

    prefixes = (
        "județul ",
        "judetul ",
        "municipiul ",
        "orașul ",
        "orasul ",
        "oras ",
        "oraș ",
    )
    for prefix in prefixes:
        if value.startswith(prefix):
            value = value[len(prefix):]

    return value.strip()


def empty_counts() -> dict[str, int]:
    return {key: 0 for key in INCIDENT_KEYS}


def get_area_profile(county: str, city: Optional[str] = None):
    county_n = normalize_text(county)
    city_n = normalize_text(city) if city else None

    with get_connection() as conn:
        cursor = conn.cursor()

        if city_n:
            cursor.execute(
                """
                SELECT
                    crime_coefficient,
                    violence_coefficient,
                    theft_coefficient,
                    traffic_coefficient,
                    emergency_coefficient
                FROM area_risk_profiles
                WHERE county = ? AND city = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (county_n, city_n),
            )
            row = cursor.fetchone()
            if row:
                return row

        cursor.execute(
            """
            SELECT
                crime_coefficient,
                violence_coefficient,
                theft_coefficient,
                traffic_coefficient,
                emergency_coefficient
            FROM area_risk_profiles
            WHERE county = ? AND city IS NULL
            ORDER BY id DESC
            LIMIT 1
            """,
            (county_n,),
        )
        return cursor.fetchone()


def get_recent_incident_counts(
    county: Optional[str] = None,
    city: Optional[str] = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> dict[str, int]:
    counts = empty_counts()

    county_n = normalize_text(county) if county else None
    city_n = normalize_text(city) if city else None

    where_parts = [
        "date(COALESCE(event_date, published_date)) >= date('now', ?)"
    ]
    params: list[Any] = [f"-{lookback_days} days"]

    if county_n and city_n:
        where_parts.append("county = ?")
        where_parts.append("(city = ? OR city IS NULL)")
        params.extend([county_n, city_n])
    elif county_n:
        where_parts.append("county = ?")
        params.append(county_n)

    where_sql = " AND ".join(where_parts)

    query = f"""
        SELECT incident_type, COUNT(*) AS total
        FROM incidents
        WHERE {where_sql}
        GROUP BY incident_type
    """

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

    for row in rows:
        incident_type = row["incident_type"]
        total = row["total"]

        if incident_type in counts:
            counts[incident_type] = total
        else:
            counts["general"] += total

    return counts


def get_weighted_incident_score(
    county: Optional[str] = None,
    city: Optional[str] = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> float:
    county_n = normalize_text(county) if county else None
    city_n = normalize_text(city) if city else None

    where_parts = [
        "date(COALESCE(event_date, published_date)) >= date('now', ?)"
    ]
    params: list[Any] = [f"-{lookback_days} days"]

    if county_n and city_n:
        where_parts.append("county = ?")
        where_parts.append("(city = ? OR city IS NULL)")
        params.extend([county_n, city_n])
    elif county_n:
        where_parts.append("county = ?")
        params.append(county_n)

    where_sql = " AND ".join(where_parts)

    query = f"""
        SELECT
            incident_type,
            COALESCE(severity_level, 'medium') AS severity_level,
            COUNT(*) AS total
        FROM incidents
        WHERE {where_sql}
        GROUP BY incident_type, COALESCE(severity_level, 'medium')
    """

    score = 0.0

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

    for row in rows:
        incident_type = row["incident_type"]
        severity = row["severity_level"]
        total = row["total"]

        base_weight = BASE_WEIGHTS.get(incident_type, BASE_WEIGHTS["general"])
        severity_multiplier = SEVERITY_MULTIPLIERS.get(severity, 1.0)

        score += total * base_weight * severity_multiplier

    return score


def def insert_source(
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
    name_n = name.strip()
    source_type_n = source_type.strip().lower()
    base_url_n = base_url.strip()

    cursor.execute("""
        SELECT id
        FROM sources
        WHERE name = ?
          AND source_type = ?
          AND base_url = ?
          AND (
                (county = ?)
                OR (county IS NULL AND ? IS NULL)
              )
          AND (
                (city = ?)
                OR (city IS NULL AND ? IS NULL)
              )
        LIMIT 1
    """, (
        name_n,
        source_type_n,
        base_url_n,
        county_n, county_n,
        city_n, city_n
    ))

    existing = cursor.fetchone()
    if existing:
        conn.close()
        return existing["id"]

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
        name_n,
        source_type_n,
        base_url_n,
        county_n,
        city_n,
        trust_level,
        is_active
    ))

    conn.commit()
    source_id = cursor.lastrowid
    conn.close()
    return source_id



def build_reason_message(counts: dict[str, int]) -> str:
    if counts["homicide"] > 0 or counts["sexual_violence"] > 0:
        return "Au fost identificate incidente violente grave în perioada recentă."
    if counts["robbery"] >= 2 or counts["violence"] >= 2:
        return "Au fost identificate incidente repetate de violență sau tâlhărie."
    if counts["theft"] >= 3:
        return "Au fost identificate furturi repetate în zona analizată."
    if counts["traffic"] >= 3:
        return "Au fost identificate incidente rutiere repetate în zona analizată."
    if counts["emergency"] >= 2:
        return "Au fost identificate urgențe recente care justifică prudență."
    return "Zona analizată nu indică în acest moment un nivel ridicat de incidente relevante."


def evaluate_risk(
    county: Optional[str],
    city: Optional[str] = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> dict[str, Any]:
    if not county:
        return {
            "level": "Date insuficiente",
            "message": "Nu s-a putut determina zona utilizatorului.",
            "incidents_summary": get_recent_incident_counts(lookback_days=lookback_days),
            "score_internal": 0.0,
        }

    profile = get_area_profile(county, city)
    counts = get_recent_incident_counts(county, city, lookback_days=lookback_days)

    if not profile:
        return {
            "level": "Date insuficiente",
            "message": "Nu există încă suficiente date pentru evaluarea zonei.",
            "incidents_summary": counts,
            "score_internal": 0.0,
        }

    crime_c = float(profile["crime_coefficient"])
    violence_c = float(profile["violence_coefficient"])
    theft_c = float(profile["theft_coefficient"])
    traffic_c = float(profile["traffic_coefficient"])
    emergency_c = float(profile["emergency_coefficient"])

    weighted_score = get_weighted_incident_score(county, city, lookback_days=lookback_days)

    adjusted_score = weighted_score
    adjusted_score += counts["violence"] * (violence_c - 1.0) * 2.0
    adjusted_score += counts["theft"] * (theft_c - 1.0) * 1.5
    adjusted_score += counts["traffic"] * (traffic_c - 1.0) * 1.2
    adjusted_score += counts["emergency"] * (emergency_c - 1.0) * 1.2
    adjusted_score *= crime_c

    # escaladare automată pentru evenimente foarte grave
    if counts["homicide"] >= 1:
        level = "Atenționare serioasă"
    elif counts["sexual_violence"] >= 1 and adjusted_score >= 8:
        level = "Atenționare serioasă"
    elif adjusted_score < 6:
        level = "Situație stabilă"
    elif adjusted_score < 12:
        level = "Prudență"
    elif adjusted_score < 20:
        level = "Prudență ridicată"
    else:
        level = "Atenționare serioasă"

    base_reason = build_reason_message(counts)

    if level == "Situație stabilă":
        message = base_reason
    elif level == "Prudență":
        message = f"{base_reason} Se recomandă atenție și prudență în deplasare."
    elif level == "Prudență ridicată":
        message = f"{base_reason} Se recomandă evitare a expunerii inutile și atenție sporită."
    else:
        message = f"{base_reason} Se recomandă vigilență maximă și evitarea zonelor sau intervalelor vulnerabile."

    return {
        "level": level,
        "message": message,
        "incidents_summary": counts,
        "score_internal": round(adjusted_score, 2),
    }