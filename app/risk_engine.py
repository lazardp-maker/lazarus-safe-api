from __future__ import annotations

from typing import Any, Optional

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

    value = " ".join(value.split())

    prefixes = (
        "județul ",
        "judetul ",
        "municipiul ",
        "orasul ",
        "orașul ",
        "oras ",
        "oraș ",
        "municipality of ",
        "county of ",
        "county ",
        "city of ",
        "comuna ",
    )
    for prefix in prefixes:
        if value.startswith(prefix):
            value = value[len(prefix):].strip()

    aliases = {
        "bucharest": "bucuresti",
        "bucurești": "bucuresti",
        "municipiul bucuresti": "bucuresti",
        "sector 1": "bucuresti",
        "sector 2": "bucuresti",
        "sector 3": "bucuresti",
        "sector 4": "bucuresti",
        "sector 5": "bucuresti",
        "sector 6": "bucuresti",
        "cluj napoca": "cluj-napoca",
        "tirgu mures": "targu mures",
        "tirgu- mures": "targu mures",
    }

    return aliases.get(value, value)


def safe_float(value: Any, default: float = 1.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def empty_counts() -> dict[str, int]:
    return {key: 0 for key in INCIDENT_KEYS}


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(value, max_value))


def get_area_profile(county: str, city: Optional[str] = None):
    county_n = normalize_text(county)
    city_n = normalize_text(city) if city else None

    if not county_n:
        return None

    with get_connection() as conn:
        cursor = conn.cursor()

        if city_n:
            cursor.execute(
                """
                SELECT
                    id,
                    county,
                    city,
                    locality_type,
                    crime_coefficient,
                    violence_coefficient,
                    theft_coefficient,
                    traffic_coefficient,
                    emergency_coefficient,
                    source_note
                FROM area_risk_profiles
                WHERE county = ?
                  AND city = ?
                  AND locality_type IN ('city', 'sector', 'commune', 'village')
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
                id,
                county,
                city,
                locality_type,
                crime_coefficient,
                violence_coefficient,
                theft_coefficient,
                traffic_coefficient,
                emergency_coefficient,
                source_note
            FROM area_risk_profiles
            WHERE county = ?
              AND (city = '' OR city IS NULL)
              AND locality_type = 'county'
            ORDER BY id DESC
            LIMIT 1
            """,
            (county_n,),
        )
        return cursor.fetchone()


def build_incident_where_clause(
    county_n: Optional[str],
    city_n: Optional[str],
    lookback_days: int,
) -> tuple[str, list[Any]]:
    where_parts = [
        "date(COALESCE(event_date, published_date)) IS NOT NULL",
        "date(COALESCE(event_date, published_date)) >= date('now', ?)",
    ]
    params: list[Any] = [f"-{lookback_days} days"]

    if county_n and city_n:
        where_parts.append("county = ?")
        where_parts.append("(city = ? OR city IS NULL OR city = '')")
        params.extend([county_n, city_n])
    elif county_n:
        where_parts.append("county = ?")
        params.append(county_n)

    return " AND ".join(where_parts), params


def get_recent_incident_counts(
    county: Optional[str] = None,
    city: Optional[str] = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> dict[str, int]:
    counts = empty_counts()

    county_n = normalize_text(county) if county else None
    city_n = normalize_text(city) if city else None

    if not county_n:
        return counts

    where_sql, params = build_incident_where_clause(county_n, city_n, lookback_days)

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
            counts[incident_type] = int(total)
        else:
            counts["general"] += int(total)

    return counts


def get_weighted_incident_score(
    county: Optional[str] = None,
    city: Optional[str] = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> float:
    county_n = normalize_text(county) if county else None
    city_n = normalize_text(city) if city else None

    if not county_n:
        return 0.0

    where_sql, params = build_incident_where_clause(county_n, city_n, lookback_days)

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
        total = int(row["total"])

        base_weight = BASE_WEIGHTS.get(incident_type, BASE_WEIGHTS["general"])
        severity_multiplier = SEVERITY_MULTIPLIERS.get(severity, 1.0)

        score += total * base_weight * severity_multiplier

    return round(score, 2)


def get_sources_used(county: Optional[str] = None, city: Optional[str] = None) -> list[str]:
    county_n = normalize_text(county) if county else None
    city_n = normalize_text(city) if city else None

    where_parts = ["is_active = 1"]
    params: list[Any] = []

    if county_n and city_n:
        where_parts.append("(county = ? OR county IS NULL)")
        where_parts.append("(city = ? OR city IS NULL OR city = '')")
        params.extend([county_n, city_n])
    elif county_n:
        where_parts.append("(county = ? OR county IS NULL)")
        params.append(county_n)

    where_sql = " AND ".join(where_parts)

    query = f"""
        SELECT name
        FROM sources
        WHERE {where_sql}
        ORDER BY trust_level DESC, name ASC
    """

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

    seen: set[str] = set()
    result: list[str] = []

    for row in rows:
        name = row["name"]
        if name and name not in seen:
            seen.add(name)
            result.append(name)

    return result


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
    if sum(counts.values()) == 0:
        return "Nu au fost identificate incidente relevante în fereastra recentă analizată."
    return "Zona analizată prezintă unele incidente recente care justifică atenție moderată."


def classify_level(adjusted_score: float, counts: dict[str, int]) -> str:
    if counts["homicide"] >= 1:
        return "Atenționare serioasă"
    if counts["sexual_violence"] >= 1 and adjusted_score >= 8:
        return "Atenționare serioasă"
    if adjusted_score < 6:
        return "Situație stabilă"
    if adjusted_score < 12:
        return "Prudență"
    if adjusted_score < 20:
        return "Prudență ridicată"
    return "Atenționare serioasă"


def evaluate_risk(
    county: Optional[str],
    city: Optional[str] = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> dict[str, Any]:
    county_n = normalize_text(county) if county else None
    city_n = normalize_text(city) if city else None

    if not county_n:
        return {
            "level": "Date insuficiente",
            "message": "Nu s-a putut determina zona utilizatorului.",
            "incidents_summary": empty_counts(),
            "score_internal": 0.0,
            "meta": {
                "county": None,
                "city": None,
                "profile_found": False,
                "lookback_days": lookback_days,
            },
        }

    profile = get_area_profile(county_n, city_n)
    counts = get_recent_incident_counts(county_n, city_n, lookback_days=lookback_days)

    if not profile:
        return {
            "level": "Date insuficiente",
            "message": "Nu există încă suficiente date pentru evaluarea zonei.",
            "incidents_summary": counts,
            "score_internal": 0.0,
            "meta": {
                "county": county_n,
                "city": city_n,
                "profile_found": False,
                "lookback_days": lookback_days,
            },
        }

    crime_c = safe_float(profile["crime_coefficient"], 1.0)
    violence_c = safe_float(profile["violence_coefficient"], 1.0)
    theft_c = safe_float(profile["theft_coefficient"], 1.0)
    traffic_c = safe_float(profile["traffic_coefficient"], 1.0)
    emergency_c = safe_float(profile["emergency_coefficient"], 1.0)

    weighted_score = get_weighted_incident_score(county_n, city_n, lookback_days=lookback_days)

    adjusted_score = weighted_score
    adjusted_score += counts["violence"] * max(0.0, violence_c - 1.0) * 2.0
    adjusted_score += counts["theft"] * max(0.0, theft_c - 1.0) * 1.5
    adjusted_score += counts["traffic"] * max(0.0, traffic_c - 1.0) * 1.2
    adjusted_score += counts["emergency"] * max(0.0, emergency_c - 1.0) * 1.2
    adjusted_score *= max(0.1, crime_c)
    adjusted_score = clamp(round(adjusted_score, 2), 0.0, 999.0)

    level = classify_level(adjusted_score, counts)
    base_reason = build_reason_message(counts)

    if level == "Situație stabilă":
        message = base_reason
    elif level == "Prudență":
        message = f"{base_reason} Se recomandă atenție și prudență în deplasare."
    elif level == "Prudență ridicată":
        message = f"{base_reason} Se recomandă evitarea expunerii inutile și atenție sporită."
    else:
        message = f"{base_reason} Se recomandă vigilență maximă și evitarea zonelor sau intervalelor vulnerabile."

    return {
        "level": level,
        "message": message,
        "incidents_summary": counts,
        "score_internal": adjusted_score,
        "meta": {
            "county": county_n,
            "city": city_n,
            "profile_found": True,
            "profile_locality_type": profile["locality_type"],
            "lookback_days": lookback_days,
            "weighted_score": weighted_score,
            "crime_coefficient": crime_c,
            "violence_coefficient": violence_c,
            "theft_coefficient": theft_c,
            "traffic_coefficient": traffic_c,
            "emergency_coefficient": emergency_c,
        },
    }