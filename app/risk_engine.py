from __future__ import annotations

import math
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

BASE_WEIGHTS = {
    "homicide": 8.0,
    "sexual_violence": 6.5,
    "robbery": 4.5,
    "violence": 3.2,
    "theft": 1.8,
    "traffic": 1.4,
    "emergency": 1.7,
    "public_order": 1.0,
    "general": 0.5,
}

SEVERITY_MULTIPLIERS = {
    "critical": 2.2,
    "high": 1.6,
    "medium": 1.0,
    "low": 0.6,
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
    }

    return aliases.get(value, value)


def safe_float(value: Any, default: float = 1.0) -> float:
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


def empty_counts() -> dict[str, int]:
    return {key: 0 for key in INCIDENT_KEYS}


def clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(value, max_value))


def haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371000.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def recency_multiplier(days_ago: Optional[int]) -> float:
    if days_ago is None:
        return 0.50
    if days_ago <= 3:
        return 1.00
    if days_ago <= 7:
        return 0.85
    if days_ago <= 14:
        return 0.70
    if days_ago <= 30:
        return 0.50
    if days_ago <= 60:
        return 0.30
    if days_ago <= 120:
        return 0.18
    return 0.10


def source_multiplier(
    verification_status: Optional[str],
    is_verified: Optional[int],
    source_priority: Optional[int],
) -> float:
    verification_status = (verification_status or "").lower()
    source_priority = safe_int(source_priority, 3)
    is_verified = safe_int(is_verified, 0)

    if is_verified == 1 and source_priority >= 5:
        return 1.00
    if verification_status == "verified":
        return 0.90
    if verification_status == "detected_by_rules":
        return 0.70 if source_priority >= 4 else 0.55
    if verification_status == "auto_parsed":
        return 0.60 if source_priority >= 4 else 0.45
    if verification_status == "ai_checked":
        return 0.55
    return 0.40


def proximity_multiplier(
    user_lat: Optional[float],
    user_lng: Optional[float],
    incident_lat: Optional[float],
    incident_lng: Optional[float],
    same_city: bool,
) -> float:
    if (
        user_lat is not None
        and user_lng is not None
        and incident_lat is not None
        and incident_lng is not None
    ):
        distance = haversine_meters(user_lat, user_lng, incident_lat, incident_lng)

        if distance <= 300:
            return 1.00
        if distance <= 1000:
            return 0.85
        if distance <= 3000:
            return 0.65
        if distance <= 10000:
            return 0.40
        return 0.20

    if same_city:
        return 1.00

    return 0.45


def heat_intensity_for_incident(incident: dict[str, Any], center_lat: float, center_lng: float) -> float:
    incident_type = incident.get("incident_type") or "general"
    severity = incident.get("severity_level") or "medium"
    days_ago = incident.get("days_ago")

    base_weight = BASE_WEIGHTS.get(incident_type, BASE_WEIGHTS["general"])
    severity_mult = SEVERITY_MULTIPLIERS.get(severity, 1.0)
    recency_mult = recency_multiplier(days_ago)
    source_mult = source_multiplier(
        verification_status=incident.get("verification_status"),
        is_verified=incident.get("is_verified"),
        source_priority=incident.get("source_priority"),
    )

    proximity_mult = proximity_multiplier(
        user_lat=center_lat,
        user_lng=center_lng,
        incident_lat=incident.get("latitude"),
        incident_lng=incident.get("longitude"),
        same_city=True,
    )

    raw = base_weight * severity_mult * recency_mult * source_mult * proximity_mult
    normalized = clamp(raw / 8.0, 0.18, 1.0)
    return round(normalized, 3)


def offset_point(lat: float, lng: float, north_m: float, east_m: float) -> tuple[float, float]:
    lat_offset = north_m / 111320.0
    cos_lat = math.cos(math.radians(lat))
    lng_offset = east_m / (111320.0 * cos_lat) if abs(cos_lat) > 1e-6 else 0.0
    return lat + lat_offset, lng + lng_offset


def synthetic_offsets(index: int) -> tuple[float, float]:
    pattern = [
        (0, 0),
        (140, 90),
        (-160, 120),
        (210, -130),
        (-240, -170),
        (320, 40),
        (-350, 70),
        (110, -260),
        (-90, 310),
        (430, -60),
        (-470, 90),
        (260, 240),
    ]
    return pattern[index % len(pattern)]


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


def get_recent_incidents_for_fallback(
    lookback_days: int,
    limit: int = 24,
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
            WHERE date(COALESCE(event_date, published_date, created_at)) IS NOT NULL
              AND date(COALESCE(event_date, published_date, created_at)) >= date('now', ?)
            ORDER BY COALESCE(date(event_date), date(published_date), date(created_at)) DESC, id DESC
            LIMIT ?
            """,
            (f"-{lookback_days} days", limit),
        )
        rows = cursor.fetchall()

    return [dict(row) for row in rows]


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


def classify_level(score: float, counts: dict[str, int]) -> str:
    if counts["homicide"] >= 1 and score >= 8:
        return "Atenționare serioasă"
    if counts["sexual_violence"] >= 1 and score >= 7:
        return "Atenționare serioasă"
    if score < 5:
        return "Situație stabilă"
    if score < 10:
        return "Prudență"
    if score < 18:
        return "Prudență ridicată"
    return "Atenționare serioasă"


def get_heatmap_points(
    center_lat: float,
    center_lng: float,
    radius_m: int = 3000,
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
                "intensity": heat_intensity_for_incident(incident, center_lat, center_lng),
            }
        )

    if points:
        return points

    # fallback: dacă nu există coordonate reale, generăm puncte sintetice în jurul locației
    fallback_incidents = get_recent_incidents_for_fallback(
        lookback_days=lookback_days,
        limit=18,
    )

    synthetic_points: list[dict[str, float]] = []

    for idx, incident in enumerate(fallback_incidents):
        north_m, east_m = synthetic_offsets(idx)
        lat_s, lng_s = offset_point(center_lat, center_lng, north_m, east_m)

        synthetic_points.append(
            {
                "lat": round(lat_s, 6),
                "lng": round(lng_s, 6),
                "intensity": heat_intensity_for_incident(incident, center_lat, center_lng),
            }
        )

    return synthetic_points


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
            },
        }

    profile = get_area_profile(county_n, city_n)
    incidents = get_recent_incidents(county_n, city_n, lookback_days)
    counts = build_counts_from_incidents(incidents)

    if not profile:
        return {
            "level": "Date insuficiente",
            "message": "Nu există încă suficiente date pentru evaluarea zonei.",
            "incidents_summary": counts,
            "score_internal": 0.0,
            "confidence": 0.30 if incidents else 0.15,
            "meta": {
                "county": county_n,
                "city": city_n,
                "profile_found": False,
                "lookback_days": lookback_days,
                "incidents_analyzed": len(incidents),
            },
        }

    crime_c = safe_float(profile["crime_coefficient"], 1.0)
    violence_c = safe_float(profile["violence_coefficient"], 1.0)
    theft_c = safe_float(profile["theft_coefficient"], 1.0)
    traffic_c = safe_float(profile["traffic_coefficient"], 1.0)
    emergency_c = safe_float(profile["emergency_coefficient"], 1.0)

    incident_score_total = 0.0

    for incident in incidents:
        incident_type = incident.get("incident_type") or "general"
        severity = incident.get("severity_level") or "medium"
        days_ago = incident.get("days_ago")

        base_weight = BASE_WEIGHTS.get(incident_type, BASE_WEIGHTS["general"])
        severity_mult = SEVERITY_MULTIPLIERS.get(severity, 1.0)
        recency_mult = recency_multiplier(days_ago)
        source_mult = source_multiplier(
            verification_status=incident.get("verification_status"),
            is_verified=incident.get("is_verified"),
            source_priority=incident.get("source_priority"),
        )

        same_city = normalize_text(incident.get("city")) == city_n if city_n else False
        proximity_mult = proximity_multiplier(
            user_lat=user_lat,
            user_lng=user_lng,
            incident_lat=incident.get("latitude"),
            incident_lng=incident.get("longitude"),
            same_city=same_city,
        )

        incident_score = base_weight * severity_mult * recency_mult * source_mult * proximity_mult
        incident_score_total += incident_score

    adjusted_score = incident_score_total
    adjusted_score += counts["violence"] * max(0.0, violence_c - 1.0) * 1.8
    adjusted_score += counts["theft"] * max(0.0, theft_c - 1.0) * 1.4
    adjusted_score += counts["traffic"] * max(0.0, traffic_c - 1.0) * 1.1
    adjusted_score += counts["emergency"] * max(0.0, emergency_c - 1.0) * 1.1
    adjusted_score *= max(0.15, crime_c)

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

    verified_count = sum(1 for item in incidents if safe_int(item.get("is_verified"), 0) == 1)

    confidence = 0.35
    confidence += 0.20 if profile else 0.0
    confidence += min(len(incidents) * 0.03, 0.20)
    confidence += min(verified_count * 0.04, 0.20)
    confidence = round(clamp(confidence, 0.0, 0.95), 2)

    return {
        "level": level,
        "message": message,
        "incidents_summary": counts,
        "score_internal": adjusted_score,
        "confidence": confidence,
        "meta": {
            "county": county_n,
            "city": city_n,
            "profile_found": True,
            "profile_locality_type": profile["locality_type"],
            "lookback_days": lookback_days,
            "incidents_analyzed": len(incidents),
            "verified_incidents": verified_count,
            "incident_score_total": round(incident_score_total, 2),
            "crime_coefficient": crime_c,
            "violence_coefficient": violence_c,
            "theft_coefficient": theft_c,
            "traffic_coefficient": traffic_c,
            "emergency_coefficient": emergency_c,
            "heatmap_mode": "real_geo" if get_incidents_near_point(
                center_lat=user_lat if user_lat is not None else 44.43,
                center_lng=user_lng if user_lng is not None else 26.10,
                radius_m=3000,
                lookback_days=lookback_days,
            ) else "synthetic_fallback",
        },
    }