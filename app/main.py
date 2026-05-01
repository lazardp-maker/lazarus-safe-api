from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Any, Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.db import get_connection, initialize_database
from app.risk_engine import evaluate_risk, get_heatmap_points


APP_VERSION = "3.4.3"
DEFAULT_LOOKBACK_DAYS = 120
DEFAULT_RADIUS_M = 10000
MAX_SERIOUS_SCAN_LIMIT = 300

SERIOUS_TYPES = {"homicide", "sexual_violence", "robbery"}

INCIDENT_TYPE_LABELS = {
    "homicide": "Omor",
    "sexual_violence": "Violență sexuală",
    "robbery": "Tâlhărie",
    "violence": "Violență",
    "theft": "Furt",
    "traffic": "Eveniment rutier",
    "emergency": "Urgență",
    "public_order": "Ordine publică",
    "general": "Eveniment raportat",
}

RISK_LEVEL_LABELS = {
    "very_low": "Situație stabilă",
    "low": "Prudență",
    "medium": "Prudență ridicată",
    "high": "Atenționare serioasă",
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        initialize_database()
    except Exception:
        pass
    yield


app = FastAPI(
    title="Lazarus Safe API",
    version=APP_VERSION,
    description="Geospatial risk intelligence backend for Lazarus Safe",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def haversine_meters(
    lat1: float,
    lng1: float,
    lat2: Optional[float],
    lng2: Optional[float],
) -> Optional[float]:
    if lat2 is None or lng2 is None:
        return None

    earth_radius_m = 6371000
    p1 = radians(lat1)
    p2 = radians(lat2)
    delta_phi = radians(lat2 - lat1)
    delta_lambda = radians(lng2 - lng1)

    a = sin(delta_phi / 2) ** 2 + cos(p1) * cos(p2) * sin(delta_lambda / 2) ** 2
    c = 2 * asin(sqrt(a))
    return round(earth_radius_m * c, 1)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_optional_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False

    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "da", "verified", "oficial"}


def row_to_dict(row: Any) -> dict[str, Any]:
    return dict(row) if row else {}


def get_table_columns(table_name: str) -> set[str]:
    conn = get_connection()
    try:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {row["name"] for row in rows}
    except Exception:
        return set()
    finally:
        conn.close()


def column_or_null(columns: set[str], column: str, alias: Optional[str] = None) -> str:
    alias_name = alias or column
    if column in columns:
        return f"{column} AS {alias_name}"
    return f"NULL AS {alias_name}"


def first_value(row: dict[str, Any], keys: tuple[str, ...]) -> Optional[str]:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def build_source_label(row: dict[str, Any]) -> str:
    return first_value(row, ("source_name", "source", "source_title", "publisher")) or "Sursă necunoscută"


def build_source_url(row: dict[str, Any]) -> Optional[str]:
    return first_value(row, ("source_url", "article_url", "url"))


def build_location_label(row: dict[str, Any]) -> str:
    city = first_value(row, ("city", "locality", "town"))
    county = first_value(row, ("county", "judet"))

    if city and county:
        return f"{city}, {county}"
    if city:
        return city
    if county:
        return county
    return "Localitate neprecizată"


def build_distance_text(distance_m: Optional[float]) -> str:
    if distance_m is None:
        return "Distanță indisponibilă"
    if distance_m < 1000:
        return f"aprox. {round(distance_m)} m"
    return f"aprox. {round(distance_m / 1000, 1)} km"


def incident_type_label(incident_type: Optional[str]) -> str:
    if not incident_type:
        return "Eveniment raportat"

    return INCIDENT_TYPE_LABELS.get(
        str(incident_type),
        str(incident_type).replace("_", " ").title(),
    )


def classify_risk_level(score: float) -> str:
    if score >= 8:
        return "high"
    if score >= 5:
        return "medium"
    if score >= 2.5:
        return "low"
    return "very_low"


def risk_badge(score: float) -> str:
    level = classify_risk_level(score)
    label = RISK_LEVEL_LABELS.get(level, "Situație analizată")
    return f"{label} · {score:.1f}/10"


def human_message(score: float, nearest_serious: Optional[dict[str, Any]]) -> str:
    if nearest_serious:
        incident_type = nearest_serious.get("incident_type")
        display_type = incident_type_label(incident_type)
        distance_text = nearest_serious.get("distance_text") or "în proximitatea zonei analizate"
        location_label = nearest_serious.get("location_label") or "zona analizată"

        if incident_type in {"homicide", "sexual_violence"}:
            return (
                f"Atenție: există un incident grav de tip {display_type.lower()} "
                f"raportat {distance_text}, în zona {location_label}. "
                f"Recomandăm prudență ridicată."
            )

        if incident_type == "robbery":
            return (
                f"Există un incident de tip tâlhărie raportat {distance_text}, "
                f"în zona {location_label}. Recomandăm prudență."
            )

    if score >= 8:
        return "Atenționare serioasă: zona prezintă risc ridicat pe baza incidentelor recente."
    if score >= 5:
        return "Prudență ridicată: au fost identificate evenimente relevante în zona analizată."
    if score >= 2.5:
        return "Prudență: există evenimente raportate, dar nivelul general rămâne moderat."

    return "Situație stabilă: nu au fost identificate incidente grave recente în proximitatea analizată."


def fetch_serious_incidents(
    lat: float,
    lng: float,
    radius_m: int = DEFAULT_RADIUS_M,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    limit: int = 20,
) -> list[dict[str, Any]]:
    columns = get_table_columns("incidents")

    if not columns:
        return []

    select_parts = [
        column_or_null(columns, "id"),
        column_or_null(columns, "incident_uid"),
        column_or_null(columns, "incident_type"),
        column_or_null(columns, "severity_level"),
        column_or_null(columns, "title"),
        column_or_null(columns, "summary"),
        column_or_null(columns, "event_date"),
        column_or_null(columns, "published_date"),
        column_or_null(columns, "days_ago"),
        column_or_null(columns, "city"),
        column_or_null(columns, "county"),
        column_or_null(columns, "locality"),
        column_or_null(columns, "town"),
        column_or_null(columns, "judet"),
        column_or_null(columns, "latitude"),
        column_or_null(columns, "longitude"),
        column_or_null(columns, "source_name"),
        column_or_null(columns, "source"),
        column_or_null(columns, "source_title"),
        column_or_null(columns, "publisher"),
        column_or_null(columns, "source_url"),
        column_or_null(columns, "article_url"),
        column_or_null(columns, "url"),
        column_or_null(columns, "is_verified"),
        column_or_null(columns, "verification_status"),
        column_or_null(columns, "source_priority"),
    ]

    query = f"""
        SELECT {", ".join(select_parts)}
        FROM incidents
        WHERE incident_type IN ('homicide', 'sexual_violence', 'robbery')
          AND COALESCE(days_ago, 99999) <= ?
        ORDER BY
            CASE incident_type
                WHEN 'homicide' THEN 1
                WHEN 'sexual_violence' THEN 2
                WHEN 'robbery' THEN 3
                ELSE 9
            END,
            COALESCE(days_ago, 99999) ASC,
            COALESCE(source_priority, 0) DESC
        LIMIT ?
    """

    conn = get_connection()
    try:
        rows = conn.execute(query, (lookback_days, MAX_SERIOUS_SCAN_LIMIT)).fetchall()
    except Exception:
        return []
    finally:
        conn.close()

    incidents: list[dict[str, Any]] = []

    for raw in rows:
        row = row_to_dict(raw)

        incident_lat = safe_optional_float(row.get("latitude"))
        incident_lng = safe_optional_float(row.get("longitude"))
        distance_m = haversine_meters(lat, lng, incident_lat, incident_lng)

        if distance_m is not None and distance_m > radius_m:
            continue

        incident_type = row.get("incident_type")
        source_url = build_source_url(row)
        source_name = build_source_label(row)
        location_label = build_location_label(row)
        distance_text = build_distance_text(distance_m)
        verification_status = str(row.get("verification_status") or "").lower()
        is_official = safe_bool(row.get("is_verified")) or verification_status == "verified"
        title = first_value(row, ("title",)) or f"{incident_type_label(incident_type)} raportat"
        days_ago = safe_int(row.get("days_ago"), 99999)
        source_priority = safe_int(row.get("source_priority"), 0)

        incidents.append(
            {
                "id": row.get("id"),
                "incident_uid": row.get("incident_uid"),
                "incident_type": incident_type,
                "display_type": incident_type_label(incident_type),
                "severity_level": row.get("severity_level"),
                "title": title,
                "display_title": title,
                "summary": row.get("summary"),
                "event_date": row.get("event_date"),
                "published_date": row.get("published_date"),
                "days_ago": days_ago,
                "city": row.get("city") or row.get("locality") or row.get("town"),
                "county": row.get("county") or row.get("judet"),
                "location_label": location_label,
                "latitude": incident_lat,
                "longitude": incident_lng,
                "distance_m": distance_m,
                "distance_text": distance_text,
                "source_name": source_name,
                "source_label": source_name,
                "source_url": source_url,
                "has_source_url": bool(source_url),
                "is_official": is_official,
                "official_badge": "OFICIAL" if is_official else "SURSĂ",
                "verification_status": row.get("verification_status"),
                "source_priority": source_priority,
                "screen_line": f"{incident_type_label(incident_type)} · {distance_text} · {location_label}",
            }
        )

    incidents.sort(
        key=lambda item: (
            item["distance_m"] if item["distance_m"] is not None else 999999999,
            item["days_ago"],
            -item["source_priority"],
        )
    )

    return incidents[:limit]


def apply_serious_minimum_score(
    base_score: float,
    serious_incidents: list[dict[str, Any]],
) -> float:
    base_score = clamp(base_score, 0.0, 10.0)

    if not serious_incidents:
        return round(base_score, 2)

    nearest_distance = serious_incidents[0].get("distance_m")
    score = base_score

    if any(item.get("incident_type") == "homicide" for item in serious_incidents):
        score = max(score, 7.0)

    if any(item.get("incident_type") == "sexual_violence" for item in serious_incidents):
        score = max(score, 6.5)

    if any(item.get("incident_type") == "robbery" for item in serious_incidents):
        score = max(score, 5.0)

    if nearest_distance is not None:
        if nearest_distance <= 500:
            score += 1.0
        elif nearest_distance <= 1500:
            score += 0.6
        elif nearest_distance <= 3000:
            score += 0.3

    return round(clamp(score, 0.0, 10.0), 2)


def normalize_base_response(base: Any) -> dict[str, Any]:
    return base if isinstance(base, dict) else {}


def build_risk_response(
    lat: float,
    lng: float,
    radius_m: int,
    lookback_days: int,
) -> dict[str, Any]:
    base: dict[str, Any] = {}
    risk_engine_error: Optional[str] = None

    try:
        base = normalize_base_response(
            evaluate_risk(
                lat=lat,
                lng=lng,
                radius_m=radius_m,
                lookback_days=lookback_days,
            )
        )
    except Exception as exc:
        risk_engine_error = str(exc)
        base = {}

    serious = fetch_serious_incidents(
        lat=lat,
        lng=lng,
        radius_m=radius_m,
        lookback_days=lookback_days,
        limit=10,
    )

    raw_score = safe_float(base.get("score", base.get("risk_score", 0)), 0.0)
    final_score = apply_serious_minimum_score(raw_score, serious)

    risk_level = classify_risk_level(final_score)
    nearest_serious = serious[0] if serious else None
    message = human_message(final_score, nearest_serious)

    return {
        "score": final_score,
        "risk_score": final_score,
        "risk_level": risk_level,
        "risk_label": RISK_LEVEL_LABELS.get(risk_level, "Situație analizată"),
        "risk_badge": risk_badge(final_score),
        "message": message,
        "screen_message": message,
        "county": base.get("county"),
        "city": base.get("city"),
        "incidents_summary": base.get("incidents_summary", {}),
        "incidents": base.get("incidents", []),
        "serious_incidents": serious,
        "nearest_serious_incident": nearest_serious,
        "sources_used": base.get("sources_used", []),
        "confidence": None,
        "display": {
            "title": RISK_LEVEL_LABELS.get(risk_level, "Situație analizată"),
            "subtitle": f"Scor risc: {final_score:.1f}/10",
            "main_message": message,
            "serious_count": len(serious),
            "nearest_serious": nearest_serious.get("screen_line") if nearest_serious else None,
        },
        "analyzed_at": now_iso(),
        "meta": {
            "radius_m": radius_m,
            "lookback_days": lookback_days,
            "app_version": APP_VERSION,
            "risk_engine_status": "fallback" if risk_engine_error else "ok",
            "risk_engine_error": risk_engine_error,
        },
    }


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "app": "Lazarus Safe API",
        "version": APP_VERSION,
        "status": "online",
        "message": "Backend activ. Folosește /health, /risk, /heatmap, /serious-incidents.",
    }


@app.get("/health")
@app.get("/health/", include_in_schema=False)
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": APP_VERSION,
        "checked_at": now_iso(),
    }


@app.get("/risk")
@app.get("/risk/", include_in_schema=False)
def risk(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_m: int = Query(DEFAULT_RADIUS_M, ge=500, le=50000),
    lookback_days: int = Query(DEFAULT_LOOKBACK_DAYS, ge=1, le=365),
) -> dict[str, Any]:
    return build_risk_response(
        lat=lat,
        lng=lng,
        radius_m=radius_m,
        lookback_days=lookback_days,
    )


@app.get("/serious-incidents")
@app.get("/serious-incidents/", include_in_schema=False)
def serious_incidents(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_m: int = Query(DEFAULT_RADIUS_M, ge=500, le=50000),
    lookback_days: int = Query(DEFAULT_LOOKBACK_DAYS, ge=1, le=365),
    limit: int = Query(20, ge=1, le=50),
) -> dict[str, Any]:
    incidents = fetch_serious_incidents(
        lat=lat,
        lng=lng,
        radius_m=radius_m,
        lookback_days=lookback_days,
        limit=limit,
    )

    return {
        "count": len(incidents),
        "nearest_serious_incident": incidents[0] if incidents else None,
        "incidents": incidents,
        "screen_title": "Incidente grave în apropiere",
        "screen_empty_message": "Nu au fost identificate incidente grave recente în zona analizată.",
        "analyzed_at": now_iso(),
        "meta": {
            "radius_m": radius_m,
            "lookback_days": lookback_days,
            "types": sorted(SERIOUS_TYPES),
            "app_version": APP_VERSION,
        },
    }


@app.get("/heatmap")
@app.get("/heatmap/", include_in_schema=False)
def heatmap(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_m: int = Query(3000, ge=500, le=50000),
    lookback_days: int = Query(DEFAULT_LOOKBACK_DAYS, ge=1, le=365),
) -> dict[str, Any]:
    try:
        points = get_heatmap_points(
            lat=lat,
            lng=lng,
            radius_m=radius_m,
            lookback_days=lookback_days,
        )
    except Exception:
        points = []

    return {
        "points": points,
        "count": len(points),
        "generated_at": now_iso(),
        "meta": {
            "radius_m": radius_m,
            "lookback_days": lookback_days,
            "app_version": APP_VERSION,
        },
    }


@app.get("/debug/routes")
def debug_routes() -> dict[str, Any]:
    return {
        "version": APP_VERSION,
        "routes": sorted([route.path for route in app.routes if hasattr(route, "path")]),
    }


@app.get("/debug/risk")
def debug_risk(
    lat: float = Query(..., ge=-90, le=90),
    lng: float = Query(..., ge=-180, le=180),
    radius_m: int = Query(DEFAULT_RADIUS_M, ge=500, le=50000),
    lookback_days: int = Query(DEFAULT_LOOKBACK_DAYS, ge=1, le=365),
) -> dict[str, Any]:
    return build_risk_response(
        lat=lat,
        lng=lng,
        radius_m=radius_m,
        lookback_days=lookback_days,
    )


@app.get("/debug/incidents")
def debug_incidents(limit: int = Query(20, ge=1, le=100)) -> dict[str, Any]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT *
            FROM incidents
            ORDER BY COALESCE(days_ago, 99999) ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    except Exception as exc:
        return {
            "count": 0,
            "error": str(exc),
            "incidents": [],
        }
    finally:
        conn.close()

    return {
        "count": len(rows),
        "incidents": [row_to_dict(row) for row in rows],
    }


@app.get("/debug/serious-all")
def debug_serious_all(limit: int = Query(50, ge=1, le=100)) -> dict[str, Any]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT *
            FROM incidents
            WHERE incident_type IN ('homicide', 'sexual_violence', 'robbery')
            ORDER BY COALESCE(days_ago, 99999) ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    except Exception as exc:
        return {
            "count": 0,
            "error": str(exc),
            "incidents": [],
        }
    finally:
        conn.close()

    return {
        "count": len(rows),
        "incidents": [row_to_dict(row) for row in rows],
    }


@app.get("/map", response_class=HTMLResponse)
def map_preview() -> str:
    return """
<!DOCTYPE html>
<html lang="ro">
<head>
    <meta charset="utf-8">
    <title>Lazarus Safe API</title>
</head>
<body style="font-family: Arial, sans-serif; padding: 32px;">
    <h2>Lazarus Safe API este activ.</h2>
    <p>Endpoint-uri disponibile:</p>
    <ul>
        <li>/health</li>
        <li>/risk?lat=44.8565&amp;lng=24.8692</li>
        <li>/heatmap?lat=44.8565&amp;lng=24.8692</li>
        <li>/serious-incidents?lat=44.8565&amp;lng=24.8692</li>
        <li>/debug/routes</li>
        <li>/debug/risk?lat=44.8565&amp;lng=24.8692</li>
        <li>/debug/serious-all</li>
    </ul>
</body>
</html>
"""