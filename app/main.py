from __future__ import annotations

from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Any, Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.db import get_connection, initialize_database
from app.risk_engine import evaluate_risk, get_heatmap_points


APP_VERSION = "3.3.0"
DEFAULT_LOOKBACK_DAYS = 120
DEFAULT_RADIUS_M = 10000

SERIOUS_TYPES = {
    "homicide",
    "sexual_violence",
    "robbery",
}


app = FastAPI(
    title="Lazarus Safe API",
    version=APP_VERSION,
    description="Geospatial risk intelligence backend for Lazarus Safe",
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


def haversine_meters(
    lat1: float,
    lng1: float,
    lat2: Optional[float],
    lng2: Optional[float],
) -> Optional[float]:
    if lat2 is None or lng2 is None:
        return None

    r = 6371000
    p1 = radians(lat1)
    p2 = radians(lat2)
    dp = radians(lat2 - lat1)
    dl = radians(lng2 - lng1)

    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    c = 2 * asin(sqrt(a))
    return round(r * c, 1)


def safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def row_to_dict(row: Any) -> dict[str, Any]:
    return dict(row) if row else {}


def get_table_columns(table_name: str) -> set[str]:
    conn = get_connection()
    try:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {row["name"] for row in rows}
    finally:
        conn.close()


def column_or_null(columns: set[str], column: str, alias: Optional[str] = None) -> str:
    alias_name = alias or column
    if column in columns:
        return f"{column} AS {alias_name}"
    return f"NULL AS {alias_name}"


def build_source_label(row: dict[str, Any]) -> str:
    for key in ["source_name", "source", "source_title", "publisher"]:
        value = row.get(key)
        if value:
            return str(value)
    return "Sursă necunoscută"


def classify_risk_level(score: float) -> str:
    if score >= 8:
        return "high"
    if score >= 5:
        return "medium"
    if score >= 2.5:
        return "low"
    return "very_low"


def human_message(score: float, serious_count: int, nearest_serious: Optional[dict[str, Any]]) -> str:
    if nearest_serious:
        incident_type = nearest_serious.get("incident_type")
        distance_m = nearest_serious.get("distance_m")
        city = nearest_serious.get("city") or nearest_serious.get("county") or "zona analizată"

        if distance_m is not None:
            distance_text = (
                f"la aproximativ {round(distance_m)} metri"
                if distance_m < 1000
                else f"la aproximativ {round(distance_m / 1000, 1)} km"
            )
        else:
            distance_text = "în proximitatea zonei analizate"

        if incident_type == "homicide":
            return f"Atenție: există un incident grav de tip omor raportat {distance_text}, în zona {city}. Recomandăm prudență ridicată."
        if incident_type == "sexual_violence":
            return f"Atenție: există un incident grav de violență sexuală raportat {distance_text}, în zona {city}. Recomandăm prudență ridicată."
        if incident_type == "robbery":
            return f"Există un incident de tâlhărie raportat {distance_text}, în zona {city}. Recomandăm prudență."

    if score >= 8:
        return "Atenționare serioasă: zona prezintă risc ridicat pe baza incidentelor recente și a severității acestora."
    if score >= 5:
        return "Prudență ridicată: au fost identificate evenimente relevante în zona analizată."
    if score >= 2.5:
        return "Prudență: zona are câteva evenimente raportate, dar nivelul general rămâne moderat."
    return "Situație stabilă: nu au fost identificate incidente grave recente în proximitatea analizată."


def fetch_serious_incidents(
    lat: float,
    lng: float,
    radius_m: int = DEFAULT_RADIUS_M,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    limit: int = 20,
) -> list[dict[str, Any]]:
    columns = get_table_columns("incidents")

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
        column_or_null(columns, "latitude"),
        column_or_null(columns, "longitude"),
        column_or_null(columns, "source_name"),
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
            COALESCE(days_ago, 99999) ASC
        LIMIT 200
    """

    conn = get_connection()
    try:
        rows = conn.execute(query, (lookback_days,)).fetchall()
    finally:
        conn.close()

    incidents: list[dict[str, Any]] = []

    for raw in rows:
        row = row_to_dict(raw)

        incident_lat = safe_float(row.get("latitude"))
        incident_lng = safe_float(row.get("longitude"))
        distance_m = haversine_meters(lat, lng, incident_lat, incident_lng)

        if distance_m is not None and distance_m > radius_m:
            continue

        source_url = (
            row.get("source_url")
            or row.get("article_url")
            or row.get("url")
        )

        incidents.append(
            {
                "id": row.get("id"),
                "incident_uid": row.get("incident_uid"),
                "incident_type": row.get("incident_type"),
                "severity_level": row.get("severity_level"),
                "title": row.get("title") or "Incident grav raportat",
                "summary": row.get("summary"),
                "event_date": row.get("event_date"),
                "published_date": row.get("published_date"),
                "days_ago": safe_int(row.get("days_ago"), 99999),
                "city": row.get("city"),
                "county": row.get("county"),
                "latitude": incident_lat,
                "longitude": incident_lng,
                "distance_m": distance_m,
                "source_name": build_source_label(row),
                "source_url": source_url,
                "is_official": bool(row.get("is_verified")) or str(row.get("verification_status")).lower() == "verified",
                "verification_status": row.get("verification_status"),
                "source_priority": safe_int(row.get("source_priority"), 0),
            }
        )

    incidents.sort(
        key=lambda x: (
            x["distance_m"] if x["distance_m"] is not None else 999999999,
            x["days_ago"],
        )
    )

    return incidents[:limit]


def apply_serious_minimum_score(
    base_score: float,
    serious_incidents: list[dict[str, Any]],
) -> float:
    if not serious_incidents:
        return base_score

    has_homicide = any(i.get("incident_type") == "homicide" for i in serious_incidents)
    has_sexual = any(i.get("incident_type") == "sexual_violence" for i in serious_incidents)
    has_robbery = any(i.get("incident_type") == "robbery" for i in serious_incidents)

    score = base_score

    if has_homicide:
        score = max(score, 6.5)

    if has_sexual:
        score = max(score, 6.0)

    if has_robbery:
        score = max(score, 4.5)

    return min(round(score, 2), 10.0)


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "app": "Lazarus Safe API",
        "version": APP_VERSION,
        "status": "online",
        "endpoints": ["/risk", "/heatmap", "/serious-incidents", "/health"],
    }


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "version": APP_VERSION,
        "checked_at": now_iso(),
    }


@app.on_event("startup")
def startup() -> None:
    initialize_database()


@app.get("/risk")
def risk(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_m: int = Query(DEFAULT_RADIUS_M),
    lookback_days: int = Query(DEFAULT_LOOKBACK_DAYS),
) -> dict[str, Any]:
    base = evaluate_risk(
        lat=lat,
        lng=lng,
        radius_m=radius_m,
        lookback_days=lookback_days,
    )

    serious = fetch_serious_incidents(
        lat=lat,
        lng=lng,
        radius_m=radius_m,
        lookback_days=lookback_days,
        limit=10,
    )

    raw_score = float(base.get("score", base.get("risk_score", 0)) or 0)
    final_score = apply_serious_minimum_score(raw_score, serious)
    nearest_serious = serious[0] if serious else None

    return {
        "score": final_score,
        "risk_score": final_score,
        "risk_level": classify_risk_level(final_score),
        "message": human_message(final_score, len(serious), nearest_serious),
        "county": base.get("county"),
        "city": base.get("city"),
        "incidents_summary": base.get("incidents_summary", {}),
        "incidents": base.get("incidents", []),
        "serious_incidents": serious,
        "nearest_serious_incident": nearest_serious,
        "sources_used": base.get("sources_used", []),
        "analyzed_at": now_iso(),
        "meta": {
            "radius_m": radius_m,
            "lookback_days": lookback_days,
            "app_version": APP_VERSION,
        },
    }


@app.get("/serious-incidents")
def serious_incidents(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_m: int = Query(DEFAULT_RADIUS_M),
    lookback_days: int = Query(DEFAULT_LOOKBACK_DAYS),
    limit: int = Query(20),
) -> dict[str, Any]:
    incidents = fetch_serious_incidents(
        lat=lat,
        lng=lng,
        radius_m=radius_m,
        lookback_days=lookback_days,
        limit=limit,
    )

    nearest = incidents[0] if incidents else None

    return {
        "count": len(incidents),
        "nearest_serious_incident": nearest,
        "incidents": incidents,
        "analyzed_at": now_iso(),
        "meta": {
            "radius_m": radius_m,
            "lookback_days": lookback_days,
            "types": list(SERIOUS_TYPES),
        },
    }


@app.get("/heatmap")
def heatmap(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_m: int = Query(3000),
    lookback_days: int = Query(DEFAULT_LOOKBACK_DAYS),
) -> dict[str, Any]:
    points = get_heatmap_points(
        lat=lat,
        lng=lng,
        radius_m=radius_m,
        lookback_days=lookback_days,
    )

    return {
        "points": points,
        "count": len(points),
        "generated_at": now_iso(),
        "meta": {
            "radius_m": radius_m,
            "lookback_days": lookback_days,
        },
    }


@app.get("/debug/incidents")
def debug_incidents(limit: int = Query(20)) -> dict[str, Any]:
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
    finally:
        conn.close()

    return {
        "count": len(rows),
        "incidents": [row_to_dict(r) for r in rows],
    }


@app.get("/debug/serious-all")
def debug_serious_all(limit: int = Query(50)) -> dict[str, Any]:
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
    finally:
        conn.close()

    return {
        "count": len(rows),
        "incidents": [row_to_dict(r) for r in rows],
    }


@app.get("/map", response_class=HTMLResponse)
def map_preview() -> str:
    return """
    <html>
      <head>
        <title>Lazarus Safe API</title>
      </head>
      <body style="font-family: Arial; padding: 32px;">
        <h2>Lazarus Safe API este activ.</h2>
        <p>Endpoint-uri disponibile:</p>
        <ul>
          <li>/risk?lat=44.8565&lng=24.8692</li>
          <li>/heatmap?lat=44.8565&lng=24.8692</li>
          <li>/serious-incidents?lat=44.8565&lng=24.8692</li>
          <li>/debug/serious-all</li>
        </ul>
      </body>
    </html>
    """GIT