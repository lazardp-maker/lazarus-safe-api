from __future__ import annotations

import math
from typing import Any, Optional

from app.db import get_connection


DEFAULT_LOOKBACK_DAYS = 60
DEFAULT_NEARBY_RADIUS_M = 3000
DEFAULT_SEVERE_RADIUS_M = 1500
DEFAULT_CRITICAL_RADIUS_M = 500

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

SEVERE_INCIDENT_TYPES = {"homicide", "sexual_violence", "robbery"}
MODERATE_INCIDENT_TYPES = {"violence", "theft", "traffic", "emergency", "public_order"}

INCIDENT_LABELS = {
    "homicide": "omor / omucidere",
    "sexual_violence": "violență sexuală",
    "robbery": "tâlhărie",
    "theft": "furt",
    "violence": "violență",
    "traffic": "accidente rutiere",
    "emergency": "situații de urgență",
    "public_order": "ordine publică",
    "general": "alte semnale",
}

BASE_WEIGHTS = {
    "homicide": 22.0,
    "sexual_violence": 19.0,
    "robbery": 15.0,
    "violence": 8.5,
    "theft": 5.0,
    "traffic": 4.2,
    "emergency": 4.5,
    "public_order": 3.5,
    "general": 1.8,
}

SEVERITY_MULTIPLIERS = {
    "critical": 1.35,
    "high": 1.15,
    "medium": 1.00,
    "low": 0.80,
}

HEATMAP_NORMALIZATION_DIVISOR = 20.0


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
        "satul ",
        "sat ",
        "localitatea ",
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
    }

    return aliases.get(value, value)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(value, max_value))


def empty_counts() -> dict[str, int]:
    return {key: 0 for key in INCIDENT_KEYS}


def haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371000.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def recency_multiplier(days_ago: Optional[int]) -> float:
    days = safe_int(days_ago, -1)

    if days < 0:
        return 0.72
    if days <= 1:
        return 1.30
    if days <= 3:
        return 1.15
    if days <= 7:
        return 1.00
    if days <= 14:
        return 0.84
    if days <= 30:
        return 0.65
    if days <= 60:
        return 0.46
    if days <= 120:
        return 0.28
    return 0.16


def source_multiplier(
    verification_status: Optional[str],
    is_verified: Optional[int],
    source_priority: Optional[int],
    ai_confidence: Optional[float],
) -> float:
    verification_status = (verification_status or "").lower().strip()
    is_verified_i = safe_int(is_verified, 0)
    source_priority_i = safe_int(source_priority, 3)
    ai_conf = clamp(safe_float(ai_confidence, 0.55), 0.20, 1.00)

    verification_part = 0.0
    if is_verified_i == 1:
        verification_part = 0.22
    elif verification_status == "verified":
        verification_part = 0.18
    elif verification_status == "detected_by_rules":
        verification_part = 0.10
    elif verification_status == "auto_parsed":
        verification_part = 0.06
    elif verification_status == "ai_checked":
        verification_part = 0.04

    priority_part = min(max(source_priority_i - 1, 0) * 0.04, 0.20)
    ai_part = (ai_conf - 0.50) * 0.30

    result = 0.70 + verification_part + priority_part + ai_part
    return clamp(result, 0.55, 1.18)


def distance_band_multiplier(distance_m: Optional[float], same_city: bool) -> float:
    if distance_m is not None:
        if distance_m <= 100:
            return 1.80
        if distance_m <= 300:
            return 1.55
        if distance_m <= 700:
            return 1.30
        if distance_m <= 1500:
            return 1.08
        if distance_m <= 3000:
            return 0.85
        if distance_m <= 7000:
            return 0.60
        if distance_m <= 15000:
            return 0.40
        return 0.20

    if same_city:
        return 0.56

    return 0.20


def format_distance(distance_m: Optional[float]) -> Optional[str]:
    if distance_m is None:
        return None

    d = float(distance_m)
    if d < 1000:
        rounded = int(round(d / 10.0) * 10)
        rounded = max(10, rounded)
        return f"{rounded} m"
    return f"{round(d / 1000.0, 1)} km"


def title_case_location(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    return " ".join(part.capitalize() for part in str(value).split())


def incident_label(incident_type: Optional[str]) -> str:
    return INCIDENT_LABELS.get(incident_type or "general", INCIDENT_LABELS["general"])


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


def get_recent_incidents(
    county: Optional[str],
    city: Optional[str],
    lookback_days: int,
) -> list[dict[str, Any]]:
    county_n = normalize_text(county) if county else None
    city_n = normalize_text(city) if city else None

    if not county_n:
        return []

    where_parts = [
        "date(COALESCE(event_date, published_date, created_at)) IS NOT NULL",
        "date(COALESCE(event_date, published_date, created_at)) >= date('now', ?)",
        "county = ?",
    ]
    params: list[Any] = [f"-{lookback_days} days", county_n]

    if city_n:
        where_parts.append("(city = ? OR city IS NULL OR city = '')")
        params.append(city_n)

    query = f"""
        SELECT
            id,
            incident_uid,
            incident_type,
            severity_level,
            title,
            summary,
            event_date,
            published_date,
            days_ago,
            city,
            county,
            latitude,
            longitude,
            ai_confidence,
            is_verified,
            verification_status,
            source_priority,
            created_at
        FROM incidents
        WHERE {" AND ".join(where_parts)}
        ORDER BY
            COALESCE(date(event_date), date(published_date), date(created_at)) DESC,
            id DESC
    """

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

    return [dict(row) for row in rows]


def get_incidents_near_point(
    center_lat: float,
    center_lng: float,
    radius_m: int,
    lookback_days: int,
) -> list[dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                id,
                incident_uid,
                incident_type,
                severity_level,
                title,
                summary,
                event_date,
                published_date,
                days_ago,
                city,
                county,
                latitude,
                longitude,
                ai_confidence,
                is_verified,
                verification_status,
                source_priority,
                created_at
            FROM incidents
            WHERE latitude IS NOT NULL
              AND longitude IS NOT NULL
              AND date(COALESCE(event_date, published_date, created_at)) IS NOT NULL
              AND date(COALESCE(event_date, published_date, created_at)) >= date('now', ?)
            ORDER BY COALESCE(date(event_date), date(published_date), date(created_at)) DESC, id DESC
            """,
            (f"-{lookback_days} days",),
        )
        rows = cursor.fetchall()

    incidents: list[dict[str, Any]] = []

    for row in rows:
        item = dict(row)
        lat = item.get("latitude")
        lng = item.get("longitude")
        if lat is None or lng is None:
            continue

        try:
            distance = haversine_meters(center_lat, center_lng, float(lat), float(lng))
        except (TypeError, ValueError):
            continue

        if distance <= radius_m:
            item["distance_m"] = round(distance, 1)
            incidents.append(item)

    return incidents


def build_counts_from_incidents(incidents: list[dict[str, Any]]) -> dict[str, int]:
    counts = empty_counts()

    for incident in incidents:
        incident_type = incident.get("incident_type")
        if incident_type in counts:
            counts[incident_type] += 1
        else:
            counts["general"] += 1

    return counts


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

    query = f"""
        SELECT name
        FROM sources
        WHERE {" AND ".join(where_parts)}
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


def enrich_incidents_with_distance(
    incidents: list[dict[str, Any]],
    user_lat: Optional[float],
    user_lng: Optional[float],
    city_n: Optional[str],
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []

    for incident in incidents:
        item = dict(incident)
        item_city_n = normalize_text(item.get("city")) if item.get("city") else None
        same_city = bool(city_n and item_city_n == city_n)

        distance_m: Optional[float] = None
        lat = item.get("latitude")
        lng = item.get("longitude")

        if (
            user_lat is not None
            and user_lng is not None
            and lat is not None
            and lng is not None
        ):
            try:
                distance_m = haversine_meters(user_lat, user_lng, float(lat), float(lng))
            except (TypeError, ValueError):
                distance_m = None

        item["same_city"] = same_city
        item["distance_m"] = round(distance_m, 1) if distance_m is not None else None
        enriched.append(item)

    return enriched


def compute_incident_risk_points(incident: dict[str, Any]) -> float:
    incident_type = incident.get("incident_type") or "general"
    severity = (incident.get("severity_level") or "medium").lower().strip()

    base_weight = BASE_WEIGHTS.get(incident_type, BASE_WEIGHTS["general"])
    severity_mult = SEVERITY_MULTIPLIERS.get(severity, 1.0)
    recency_mult = recency_multiplier(incident.get("days_ago"))
    source_mult = source_multiplier(
        verification_status=incident.get("verification_status"),
        is_verified=incident.get("is_verified"),
        source_priority=incident.get("source_priority"),
        ai_confidence=incident.get("ai_confidence"),
    )
    distance_mult = distance_band_multiplier(
        distance_m=incident.get("distance_m"),
        same_city=bool(incident.get("same_city")),
    )

    return base_weight * severity_mult * recency_mult * source_mult * distance_mult


def compute_heat_intensity(incident: dict[str, Any], center_lat: float, center_lng: float) -> float:
    item = dict(incident)

    lat = item.get("latitude")
    lng = item.get("longitude")
    if lat is not None and lng is not None:
        try:
            item["distance_m"] = haversine_meters(center_lat, center_lng, float(lat), float(lng))
        except (TypeError, ValueError):
            item["distance_m"] = None
    else:
        item["distance_m"] = None

    item["same_city"] = True

    raw = compute_incident_risk_points(item)
    normalized = clamp(raw / HEATMAP_NORMALIZATION_DIVISOR, 0.15, 1.0)
    return round(normalized, 3)


def find_closest_severe_incident(incidents: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    severe = [
        item
        for item in incidents
        if item.get("incident_type") in SEVERE_INCIDENT_TYPES and item.get("distance_m") is not None
    ]
    if not severe:
        return None
    return min(severe, key=lambda x: float(x["distance_m"]))


def summarize_severity_groups(counts: dict[str, int]) -> tuple[int, int]:
    severe_count = sum(counts.get(key, 0) for key in SEVERE_INCIDENT_TYPES)
    moderate_count = sum(counts.get(key, 0) for key in MODERATE_INCIDENT_TYPES)
    return severe_count, moderate_count


def score_floor_from_severity(
    counts: dict[str, int],
    closest_severe: Optional[dict[str, Any]],
) -> float:
    severe_count, moderate_count = summarize_severity_groups(counts)
    floor = 0.0

    homicide_count = counts.get("homicide", 0)
    sexual_count = counts.get("sexual_violence", 0)
    robbery_count = counts.get("robbery", 0)

    if homicide_count > 0:
        floor = max(floor, 8.2)
    if sexual_count > 0:
        floor = max(floor, 7.4)
    if robbery_count > 0:
        floor = max(floor, 6.4)

    if severe_count >= 2:
        floor = max(floor, 7.0)
    elif severe_count == 1:
        floor = max(floor, 5.8)

    if moderate_count >= 5:
        floor = max(floor, 4.2)
    elif moderate_count >= 2:
        floor = max(floor, 2.2)

    if closest_severe is not None:
        distance_m = safe_float(closest_severe.get("distance_m"), 999999.0)
        incident_type = closest_severe.get("incident_type")

        if incident_type == "homicide":
            if distance_m <= 300:
                floor = max(floor, 9.0)
            elif distance_m <= 1500:
                floor = max(floor, 8.4)

        elif incident_type == "sexual_violence":
            if distance_m <= 300:
                floor = max(floor, 8.3)
            elif distance_m <= 1500:
                floor = max(floor, 7.6)

        elif incident_type == "robbery":
            if distance_m <= 300:
                floor = max(floor, 7.2)
            elif distance_m <= 1500:
                floor = max(floor, 6.6)

    return floor


def build_reason_message(
    counts: dict[str, int],
    closest_severe: Optional[dict[str, Any]],
    nearby_geo_incidents: list[dict[str, Any]],
    lookback_days: int,
    confidence: float,
) -> str:
    severe_count, moderate_count = summarize_severity_groups(counts)

    if closest_severe is not None:
        label = incident_label(closest_severe.get("incident_type"))
        distance_text = format_distance(closest_severe.get("distance_m")) or "aproape"
        days = closest_severe.get("days_ago")

        if days is None:
            time_text = "recent"
        else:
            days_i = safe_int(days, 999)
            if days_i <= 1:
                time_text = "în ultimele 24 de ore"
            elif days_i <= 7:
                time_text = f"în ultimele {days_i} zile"
            elif days_i <= 30:
                time_text = "în ultima lună"
            else:
                time_text = f"în ultimele {lookback_days} zile"

        return (
            f"La aproximativ {distance_text} de această locație a fost raportat "
            f"un caz de {label} {time_text}."
        )

    if severe_count > 0:
        if severe_count == 1:
            return (
                f"În zona analizată a fost identificat 1 incident grav "
                f"în ultimele {lookback_days} zile."
            )
        return (
            f"În zona analizată au fost identificate {severe_count} incidente grave "
            f"în ultimele {lookback_days} zile."
        )

    if moderate_count >= 4:
        return (
            f"În apropiere au fost raportate mai multe incidente relevante "
            f"în ultimele {lookback_days} zile."
        )

    if moderate_count > 0:
        return (
            "Au fost identificate incidente izolate în zona analizată. "
            "Nu rezultă un semnal critic, dar este recomandată atenție moderată."
        )

    if nearby_geo_incidents:
        return (
            "Nu au fost identificate incidente grave în proximitatea imediată, "
            "dar există semnale limitate în zona extinsă analizată."
        )

    if confidence < 0.35:
        return (
            "Nu au fost identificate incidente relevante, însă volumul de date disponibil "
            "pentru această zonă este încă limitat."
        )

    return (
        f"Nu au fost identificate incidente grave sau semnale relevante "
        f"în proximitatea analizată în ultimele {lookback_days} zile."
    )


def classify_level(
    score_0_10: float,
    counts: dict[str, int],
    closest_severe: Optional[dict[str, Any]],
    confidence: float,
) -> str:
    severe_count, moderate_count = summarize_severity_groups(counts)

    if confidence < 0.20 and severe_count == 0 and moderate_count == 0:
        return "Date insuficiente"

    if closest_severe is not None:
        distance_m = safe_float(closest_severe.get("distance_m"), 999999.0)
        incident_type = closest_severe.get("incident_type")

        if incident_type == "homicide" and distance_m <= DEFAULT_SEVERE_RADIUS_M:
            return "Atenționare serioasă"
        if incident_type == "sexual_violence" and distance_m <= DEFAULT_SEVERE_RADIUS_M:
            return "Atenționare serioasă"
        if incident_type == "robbery" and distance_m <= DEFAULT_CRITICAL_RADIUS_M:
            return "Atenționare serioasă"

    if severe_count >= 2:
        return "Atenționare serioasă"

    if severe_count == 1:
        if score_0_10 >= 7.0:
            return "Atenționare serioasă"
        return "Prudență ridicată"

    if score_0_10 >= 7.5:
        return "Atenționare serioasă"
    if score_0_10 >= 4.2:
        return "Prudență ridicată"
    if score_0_10 >= 1.8 or moderate_count >= 2:
        return "Prudență"

    return "Situație stabilă"


def build_ui_message(level: str, base_reason: str, confidence: float) -> str:
    if level == "Date insuficiente":
        return (
            f"{base_reason} Evaluarea este orientativă deoarece există încă puține date "
            "disponibile pentru această zonă."
        )

    if level == "Situație stabilă":
        if confidence < 0.35:
            return (
                f"{base_reason} Zona pare stabilă în acest moment, dar nivelul de încredere "
                "al evaluării este încă limitat."
            )
        return f"{base_reason} Zona este considerată stabilă în acest moment."

    if level == "Prudență":
        return (
            f"{base_reason} Se recomandă atenție normală și evitarea expunerii inutile, "
            "mai ales în intervale vulnerabile."
        )

    if level == "Prudență ridicată":
        return (
            f"{base_reason} Se recomandă vigilență sporită și evitarea deplasărilor "
            "neesențiale în intervale vulnerabile."
        )

    return (
        f"{base_reason} Se recomandă vigilență maximă și evitarea zonelor sau "
        "intervalelor vulnerabile."
    )


def normalize_score_to_ten(raw_score: float) -> float:
    """
    Transformă scorul brut într-o scară 0–10.
    Funcția logaritmică:
    - evită scoruri 0 când există risc real,
    - evită saturarea prea rapidă la 10 în zonele urbane dense.
    """
    if raw_score <= 0:
        return 0.0

    normalized = 10.0 * (1 - math.exp(-raw_score / 24.0))
    return round(clamp(normalized, 0.0, 10.0), 1)


def get_heatmap_points(
    center_lat: float,
    center_lng: float,
    radius_m: int = DEFAULT_NEARBY_RADIUS_M,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> list[dict[str, float]]:
    incidents_geo = get_incidents_near_point(
        center_lat=center_lat,
        center_lng=center_lng,
        radius_m=radius_m,
        lookback_days=lookback_days,
    )

    points: list[dict[str, float]] = []

    for incident in incidents_geo:
        lat = incident.get("latitude")
        lng = incident.get("longitude")
        if lat is None or lng is None:
            continue

        points.append(
            {
                "lat": float(lat),
                "lng": float(lng),
                "intensity": compute_heat_intensity(incident, center_lat, center_lng),
            }
        )

    return points


def evaluate_risk(
    county: Optional[str],
    city: Optional[str] = None,
    user_lat: Optional[float] = None,
    user_lng: Optional[float] = None,
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
            "confidence": 0.20,
            "meta": {
                "county": None,
                "city": None,
                "profile_found": False,
                "lookback_days": lookback_days,
                "incidents_analyzed": 0,
                "nearby_incidents_analyzed": 0,
                "severe_nearby_count": 0,
                "closest_severe_incident": None,
                "heatmap_mode": "real_geo_only",
            },
        }

    profile = get_area_profile(county_n, city_n)
    incidents_area = get_recent_incidents(county_n, city_n, lookback_days)
    incidents_area_enriched = enrich_incidents_with_distance(
        incidents=incidents_area,
        user_lat=user_lat,
        user_lng=user_lng,
        city_n=city_n,
    )

    counts = build_counts_from_incidents(incidents_area_enriched)

    nearby_geo_incidents: list[dict[str, Any]] = []
    if user_lat is not None and user_lng is not None:
        nearby_geo_incidents = get_incidents_near_point(
            center_lat=user_lat,
            center_lng=user_lng,
            radius_m=DEFAULT_NEARBY_RADIUS_M,
            lookback_days=lookback_days,
        )
        nearby_geo_incidents = enrich_incidents_with_distance(
            incidents=nearby_geo_incidents,
            user_lat=user_lat,
            user_lng=user_lng,
            city_n=city_n,
        )

    severe_geo_incidents = [
        item for item in nearby_geo_incidents
        if item.get("incident_type") in SEVERE_INCIDENT_TYPES
    ]
    closest_severe = find_closest_severe_incident(nearby_geo_incidents)

    if not profile and not incidents_area_enriched and not nearby_geo_incidents:
        return {
            "level": "Date insuficiente",
            "message": "Nu există încă suficiente date pentru evaluarea acestei zone.",
            "incidents_summary": counts,
            "score_internal": 0.0,
            "confidence": 0.18,
            "meta": {
                "county": county_n,
                "city": city_n,
                "profile_found": False,
                "lookback_days": lookback_days,
                "incidents_analyzed": 0,
                "nearby_incidents_analyzed": 0,
                "severe_nearby_count": 0,
                "closest_severe_incident": None,
                "heatmap_mode": "real_geo_only",
            },
        }

    crime_c = safe_float(profile["crime_coefficient"], 1.0) if profile else 1.0
    violence_c = safe_float(profile["violence_coefficient"], 1.0) if profile else 1.0
    theft_c = safe_float(profile["theft_coefficient"], 1.0) if profile else 1.0
    traffic_c = safe_float(profile["traffic_coefficient"], 1.0) if profile else 1.0
    emergency_c = safe_float(profile["emergency_coefficient"], 1.0) if profile else 1.0

    incident_score_total = 0.0
    for incident in incidents_area_enriched:
        points = compute_incident_risk_points(incident)
        incident_type = incident.get("incident_type") or "general"

        if incident_type in {"violence", "homicide", "sexual_violence", "robbery"}:
            points *= max(1.0, violence_c)
        elif incident_type == "theft":
            points *= max(1.0, theft_c)
        elif incident_type == "traffic":
            points *= max(1.0, traffic_c)
        elif incident_type == "emergency":
            points *= max(1.0, emergency_c)

        incident_score_total += points

    profile_modifier = max(0.82, crime_c)
    raw_score = incident_score_total * profile_modifier

    if closest_severe is not None:
        distance_m = safe_float(closest_severe.get("distance_m"), 999999.0)
        incident_type = closest_severe.get("incident_type")

        if incident_type == "homicide":
            if distance_m <= 150:
                raw_score += 24.0
            elif distance_m <= 300:
                raw_score += 20.0
            elif distance_m <= 700:
                raw_score += 16.0
            elif distance_m <= 1500:
                raw_score += 11.0

        elif incident_type == "sexual_violence":
            if distance_m <= 150:
                raw_score += 21.0
            elif distance_m <= 300:
                raw_score += 17.0
            elif distance_m <= 700:
                raw_score += 13.0
            elif distance_m <= 1500:
                raw_score += 9.0

        elif incident_type == "robbery":
            if distance_m <= 150:
                raw_score += 16.0
            elif distance_m <= 300:
                raw_score += 13.0
            elif distance_m <= 700:
                raw_score += 10.0
            elif distance_m <= 1500:
                raw_score += 7.0

    raw_score += min(len(severe_geo_incidents) * 2.8, 12.0)

    preliminary_score_0_10 = normalize_score_to_ten(raw_score)
    score_floor = score_floor_from_severity(counts, closest_severe)
    score_0_10 = round(max(preliminary_score_0_10, score_floor), 1)

    verified_count = sum(1 for item in incidents_area_enriched if safe_int(item.get("is_verified"), 0) == 1)
    geo_count = sum(
        1
        for item in incidents_area_enriched
        if item.get("latitude") is not None and item.get("longitude") is not None
    )

    confidence = 0.24
    confidence += 0.18 if profile else 0.0
    confidence += min(len(incidents_area_enriched) * 0.02, 0.16)
    confidence += min(verified_count * 0.03, 0.18)
    confidence += min(geo_count * 0.02, 0.15)

    if city_n and not any(item.get("city") for item in incidents_area_enriched):
        confidence -= 0.04

    confidence = round(clamp(confidence, 0.0, 0.97), 2)

    level = classify_level(
        score_0_10=score_0_10,
        counts=counts,
        closest_severe=closest_severe,
        confidence=confidence,
    )

    base_reason = build_reason_message(
        counts=counts,
        closest_severe=closest_severe,
        nearby_geo_incidents=nearby_geo_incidents,
        lookback_days=lookback_days,
        confidence=confidence,
    )
    message = build_ui_message(level, base_reason, confidence)

    closest_severe_payload = None
    if closest_severe is not None:
        closest_severe_payload = {
            "incident_type": closest_severe.get("incident_type"),
            "incident_label": incident_label(closest_severe.get("incident_type")),
            "distance_m": round(safe_float(closest_severe.get("distance_m"), 0.0), 1),
            "distance_text": format_distance(closest_severe.get("distance_m")),
            "days_ago": closest_severe.get("days_ago"),
            "city": closest_severe.get("city"),
            "county": closest_severe.get("county"),
            "title": closest_severe.get("title"),
            "summary": closest_severe.get("summary"),
            "latitude": closest_severe.get("latitude"),
            "longitude": closest_severe.get("longitude"),
        }

    severe_count, moderate_count = summarize_severity_groups(counts)

    return {
        "level": level,
        "message": message,
        "incidents_summary": counts,
        "score_internal": score_0_10,
        "confidence": confidence,
        "meta": {
            "county": county_n,
            "city": city_n,
            "profile_found": bool(profile),
            "profile_locality_type": profile["locality_type"] if profile else None,
            "lookback_days": lookback_days,
            "incidents_analyzed": len(incidents_area_enriched),
            "nearby_incidents_analyzed": len(nearby_geo_incidents),
            "verified_incidents": verified_count,
            "geo_coded_incidents": geo_count,
            "severe_count": severe_count,
            "moderate_count": moderate_count,
            "severe_nearby_count": len(severe_geo_incidents),
            "raw_score": round(raw_score, 2),
            "preliminary_score_0_10": preliminary_score_0_10,
            "score_floor": score_floor,
            "incident_score_total": round(incident_score_total, 2),
            "crime_coefficient": crime_c,
            "violence_coefficient": violence_c,
            "theft_coefficient": theft_c,
            "traffic_coefficient": traffic_c,
            "emergency_coefficient": emergency_c,
            "closest_severe_incident": closest_severe_payload,
            "heatmap_mode": "real_geo_only",
            "recommended_ui_flags": {
                "show_closest_severe_banner": closest_severe_payload is not None,
                "show_distance_to_severe": closest_severe_payload is not None,
                "show_stable_label": level == "Situație stabilă",
                "show_insufficient_data_hint": level == "Date insuficiente" or confidence < 0.35,
            },
        },
    }