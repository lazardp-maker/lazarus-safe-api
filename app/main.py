from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.db import (
    get_connection,
    get_db_path,
    initialize_database,
    list_tables,
    validate_critical_tables,
)
from app.risk_engine import (
    evaluate_risk,
    get_heatmap_points,
    get_sources_used,
    get_serious_incidents_for_location,
    user_friendly_explanation,
)
from app.schemas import AnalyzeRequest, AnalyzeResponse, ClosestSevereIncident

APP_NAME = "Lazarus Safe API"
APP_VERSION = os.getenv("APP_VERSION", "3.5.1")
APP_ENV = os.getenv("APP_ENV", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
GEOCODER_TIMEOUT_SECONDS = int(os.getenv("GEOCODER_TIMEOUT_SECONDS", "10"))

logger = logging.getLogger(APP_NAME)
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=(
        "API pentru evaluarea riscului de securitate fizică pe baza locației, "
        "cu suport pentru analiză geospațială, surse citate și explicații pe înțelesul utilizatorului."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event() -> None:
    logger.info("startup.begin env=%s version=%s", APP_ENV, APP_VERSION)

    try:
        initialize_database()
        validate_critical_tables()
        logger.info("database.initialized path=%s", get_db_path())
    except Exception as exc:
        logger.exception("startup.database_failed error=%s", exc)
        raise

    try:
        with get_connection() as conn:
            tables = list_tables(conn)
            logger.info("database.tables_found count=%s tables=%s", len(tables), tables)
    except Exception as exc:
        logger.exception("startup.db_inspection_failed error=%s", exc)

    logger.info("startup.complete")


@app.on_event("shutdown")
def shutdown_event() -> None:
    logger.info("shutdown.complete")


def normalize_text(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    value = value.strip().lower()
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

    return " ".join(value.split())


def canonicalize_place(value: Optional[str]) -> Optional[str]:
    value = normalize_text(value)
    if not value:
        return None

    prefixes = [
        "municipiul ",
        "judetul ",
        "judet ",
        "orasul ",
        "oras ",
        "comuna ",
        "satul ",
        "localitatea ",
        "county of ",
        "county ",
    ]

    for prefix in prefixes:
        if value.startswith(prefix):
            value = value[len(prefix):].strip()

    aliases = {
        "bucharest": "bucuresti",
        "municipiul bucuresti": "bucuresti",
        "orasul bucuresti": "bucuresti",
        "sector 1": "sector 1",
        "sector 2": "sector 2",
        "sector 3": "sector 3",
        "sector 4": "sector 4",
        "sector 5": "sector 5",
        "sector 6": "sector 6",
        "cluj napoca": "cluj-napoca",
        "tirgu mures": "targu mures",
    }

    value = aliases.get(value, value)

    if value in {"sector 1", "sector 2", "sector 3", "sector 4", "sector 5", "sector 6"}:
        return value

    return value


def validate_coordinates(lat: float, lng: float) -> None:
    if not (-90 <= lat <= 90):
        raise HTTPException(status_code=422, detail="Latitudine invalidă.")
    if not (-180 <= lng <= 180):
        raise HTTPException(status_code=422, detail="Longitudine invalidă.")


def reverse_geocode_real(lat: float, lng: float) -> tuple[Optional[str], Optional[str]]:
    validate_coordinates(lat, lng)

    url = "https://nominatim.openstreetmap.org/reverse"
    headers = {
        "User-Agent": f"LazarusSafeApp/{APP_VERSION} (contact: lazardp@gmail.com)",
        "Accept": "application/json",
    }
    params = {
        "lat": lat,
        "lon": lng,
        "format": "jsonv2",
        "addressdetails": 1,
        "accept-language": "ro",
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=GEOCODER_TIMEOUT_SECONDS)
        response.raise_for_status()

        data = response.json()
        address = data.get("address", {})

        raw_county = address.get("county") or address.get("state_district") or address.get("state")
        raw_city = (
            address.get("city")
            or address.get("municipality")
            or address.get("town")
            or address.get("village")
            or address.get("suburb")
            or address.get("city_district")
            or address.get("borough")
        )

        county = canonicalize_place(raw_county)
        city = canonicalize_place(raw_city)

        if city in {"sector 1", "sector 2", "sector 3", "sector 4", "sector 5", "sector 6"}:
            county = "bucuresti"

        if county == "bucuresti" and not city:
            city = "bucuresti"

        if county:
            return county, city

    except Exception as exc:
        logger.warning("reverse_geocode.failed lat=%s lng=%s error=%s", lat, lng, exc)

    if 44.3 <= lat <= 44.6 and 25.9 <= lng <= 26.3:
        return "bucuresti", "bucuresti"

    if 44.7 <= lat <= 45.0 and 24.7 <= lng <= 25.1:
        return "arges", "pitesti"

    return None, None


def empty_incidents_summary() -> dict[str, int]:
    return {
        "homicide": 0,
        "sexual_violence": 0,
        "robbery": 0,
        "theft": 0,
        "violence": 0,
        "traffic": 0,
        "emergency": 0,
        "public_order": 0,
        "general": 0,
    }


def model_to_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return {}


def incidents_summary_to_dict(value: Any) -> dict[str, int]:
    summary = model_to_dict(value)
    default_summary = empty_incidents_summary()

    for key, val in summary.items():
        try:
            default_summary[key] = int(val)
        except Exception:
            continue

    return default_summary


def build_closest_payload(closest_raw: Any) -> Optional[ClosestSevereIncident]:
    if not isinstance(closest_raw, dict):
        return None

    return ClosestSevereIncident(
        incident_id=closest_raw.get("incident_id"),
        incident_type=closest_raw.get("incident_type"),
        incident_label=closest_raw.get("incident_label"),
        distance_m=closest_raw.get("distance_m"),
        distance_text=closest_raw.get("distance_text"),
        days_ago=closest_raw.get("days_ago"),
        city=closest_raw.get("city"),
        county=closest_raw.get("county"),
        title=closest_raw.get("title"),
        summary=closest_raw.get("summary"),
        latitude=closest_raw.get("latitude"),
        longitude=closest_raw.get("longitude"),
        published_date=closest_raw.get("published_date"),
        official_confirmation=bool(closest_raw.get("official_confirmation", False)),
        primary_source_name=closest_raw.get("primary_source_name"),
        primary_source_type=closest_raw.get("primary_source_type"),
        primary_source_url=closest_raw.get("primary_source_url"),
        primary_source_title=closest_raw.get("primary_source_title"),
    )


def build_analysis_response(payload: AnalyzeRequest) -> AnalyzeResponse:
    analyzed_at = datetime.now(timezone.utc).isoformat()
    county, city = reverse_geocode_real(payload.lat, payload.lng)

    if not county:
        return AnalyzeResponse(
            level="Date insuficiente",
            score=0.0,
            message="Nu am putut identifica județul sau localitatea pentru coordonatele primite.",
            county=None,
            city=None,
            incidents_summary=empty_incidents_summary(),
            incidents_count=0,
            sources_used=[],
            confidence=0.0,
            confidence_percent=0.0,
            closest_severe_incident=None,
            analyzed_at=analyzed_at,
            debug={"reason": "reverse_geocode_failed", "input_lat": payload.lat, "input_lng": payload.lng},
        )

    try:
        result = evaluate_risk(county=county, city=city, user_lat=payload.lat, user_lng=payload.lng)
        sources_used = get_sources_used(county, city)
    except Exception as exc:
        logger.exception("risk_engine.failed county=%s city=%s error=%s", county, city, exc)
        return AnalyzeResponse(
            level="Date insuficiente",
            score=0.0,
            message="Locația a fost identificată, dar analiza de risc a eșuat.",
            county=county,
            city=city,
            incidents_summary=empty_incidents_summary(),
            incidents_count=0,
            sources_used=[],
            confidence=0.0,
            confidence_percent=0.0,
            closest_severe_incident=None,
            analyzed_at=analyzed_at,
            debug={"reason": "risk_engine_failed", "error": str(exc), "county": county, "city": city},
        )

    if not isinstance(result, dict):
        return AnalyzeResponse(
            level="Date insuficiente",
            score=0.0,
            message="Analiza nu a returnat un rezultat valid.",
            county=county,
            city=city,
            incidents_summary=empty_incidents_summary(),
            incidents_count=0,
            sources_used=[],
            confidence=0.0,
            confidence_percent=0.0,
            closest_severe_incident=None,
            analyzed_at=analyzed_at,
            debug={"reason": "invalid_risk_result", "county": county, "city": city},
        )

    incidents_summary = incidents_summary_to_dict(result.get("incidents_summary", empty_incidents_summary()))
    incidents_count = sum(int(v) for v in incidents_summary.values())
    confidence_raw = float(result.get("confidence", 0.0) or 0.0)

    return AnalyzeResponse(
        level=result.get("level", "Date insuficiente"),
        score=float(result.get("score_internal", 0.0) or 0.0),
        message=result.get("message", "Analiza nu a putut fi completată."),
        county=county,
        city=city,
        incidents_summary=incidents_summary,
        incidents_count=incidents_count,
        sources_used=sources_used if isinstance(sources_used, list) else [],
        confidence=confidence_raw,
        confidence_percent=round(confidence_raw * 100.0, 1),
        closest_severe_incident=build_closest_payload(result.get("closest_severe_incident")),
        analyzed_at=analyzed_at,
        debug=result.get("meta") if isinstance(result.get("meta"), dict) else {},
    )


def build_human_risk_payload(result: AnalyzeResponse) -> dict[str, Any]:
    debug = result.debug if isinstance(result.debug, dict) else {}
    severe_count = int(debug.get("severe_count", 0) or 0)
    lookback_days = int(debug.get("lookback_days", 60) or 60)

    closest_dict = model_to_dict(result.closest_severe_incident) if result.closest_severe_incident else None

    friendly = user_friendly_explanation(
        level=result.level,
        score=result.score,
        confidence=result.confidence,
        incidents_count=result.incidents_count,
        severe_count=severe_count,
        closest_severe=closest_dict,
        lookback_days=lookback_days,
    )

    return {
        "human_title": friendly.get("title"),
        "score_text": friendly.get("score_text"),
        "data_quality_label": friendly.get("data_quality_label"),
        "risk_reasons": friendly.get("reasons", []),
        "map_legend": friendly.get("legend", []),
        "heatmap_note": friendly.get("important_note"),
        "serious_incidents_count": severe_count,
        "lookback_days": lookback_days,
    }


@app.get("/health")
def health() -> dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total FROM sources")
        sources_total = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) AS total FROM area_risk_profiles")
        profiles_total = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) AS total FROM incidents")
        incidents_total = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) AS total FROM articles")
        articles_total = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) AS total FROM incidents WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
        geo_incidents_total = cursor.fetchone()["total"]

    return {
        "status": "ok",
        "service": APP_NAME,
        "version": APP_VERSION,
        "environment": APP_ENV,
        "db_path": get_db_path(),
        "stats": {
            "sources": sources_total,
            "area_risk_profiles": profiles_total,
            "incidents": incidents_total,
            "geo_coded_incidents": geo_incidents_total,
            "articles": articles_total,
        },
    }


@app.get("/ready")
def ready() -> dict[str, Any]:
    try:
        with get_connection() as conn:
            tables = list_tables(conn)

        required_tables = {"sources", "area_risk_profiles", "incidents", "articles", "incident_mentions"}
        missing_tables = sorted(required_tables - set(tables))

        return {
            "status": "ok" if not missing_tables else "degraded",
            "service": APP_NAME,
            "version": APP_VERSION,
            "missing_tables": missing_tables,
        }
    except Exception as exc:
        logger.exception("ready.failed error=%s", exc)
        raise HTTPException(status_code=500, detail=f"Readiness check failed: {exc}")


@app.get("/debug/db")
def debug_db() -> dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()
        tables = list_tables(conn)

        columns: dict[str, list[str]] = {}
        for table_name in tables:
            try:
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns[table_name] = [row["name"] for row in cursor.fetchall()]
            except Exception:
                columns[table_name] = []

    return {"db_path": get_db_path(), "tables": tables, "columns": columns}


@app.get("/admin/db-summary")
def admin_db_summary() -> dict[str, Any]:
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) AS total FROM sources")
        sources_total = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) AS total FROM articles")
        articles_total = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) AS total FROM incidents")
        incidents_total = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) AS total FROM incident_mentions")
        mentions_total = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) AS total FROM area_risk_profiles")
        profiles_total = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) AS total FROM incidents WHERE latitude IS NOT NULL AND longitude IS NOT NULL")
        geo_incidents_total = cursor.fetchone()["total"]

        cursor.execute(
            """
            SELECT verification_status, COUNT(*) AS total
            FROM incidents
            GROUP BY verification_status
            ORDER BY total DESC
            """
        )
        by_verification = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            """
            SELECT incident_type, COUNT(*) AS total
            FROM incidents
            GROUP BY incident_type
            ORDER BY total DESC
            """
        )
        by_type = [dict(row) for row in cursor.fetchall()]

        cursor.execute(
            """
            SELECT county, COUNT(*) AS total
            FROM incidents
            WHERE county IS NOT NULL AND county <> ''
            GROUP BY county
            ORDER BY total DESC
            LIMIT 20
            """
        )
        by_county = [dict(row) for row in cursor.fetchall()]

    return {
        "db_path": get_db_path(),
        "totals": {
            "sources": sources_total,
            "articles": articles_total,
            "incidents": incidents_total,
            "incident_mentions": mentions_total,
            "area_risk_profiles": profiles_total,
            "geo_coded_incidents": geo_incidents_total,
        },
        "incidents_by_verification_status": by_verification,
        "incidents_by_type": by_type,
        "incidents_by_county": by_county,
    }


@app.get("/admin/recent-incidents")
def admin_recent_incidents(
    limit: int = Query(default=20, ge=1, le=100),
    county: Optional[str] = Query(default=None),
    city: Optional[str] = Query(default=None),
    only_geocoded: bool = Query(default=False),
) -> dict[str, Any]:
    county_n = canonicalize_place(county) if county else None
    city_n = canonicalize_place(city) if city else None

    where_parts = ["1=1"]
    params: list[object] = []

    if county_n:
        where_parts.append("county = ?")
        params.append(county_n)
    if city_n:
        where_parts.append("city = ?")
        params.append(city_n)
    if only_geocoded:
        where_parts.append("latitude IS NOT NULL AND longitude IS NOT NULL")

    query = f"""
        SELECT *
        FROM incidents
        WHERE {" AND ".join(where_parts)}
        ORDER BY COALESCE(date(event_date), date(published_date), date(created_at)) DESC, id DESC
        LIMIT ?
    """
    params.append(limit)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

    return {
        "count": len(rows),
        "filters": {"county": county_n, "city": city_n, "limit": limit, "only_geocoded": only_geocoded},
        "items": [dict(row) for row in rows],
    }


@app.post("/admin/run-collector")
def admin_run_collector() -> dict[str, str]:
    try:
        logger.info("collector.manual_run.begin")
        from app.collectors.collector_real import main as run_collector

        run_collector()
        logger.info("collector.manual_run.complete")
        return {"status": "ok", "message": "Collectorul a rulat cu succes."}
    except Exception as exc:
        logger.exception("collector.manual_run.failed error=%s", exc)
        raise HTTPException(status_code=500, detail=f"Eroare la rularea collectorului: {exc}")


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    validate_coordinates(payload.lat, payload.lng)
    return build_analysis_response(payload)


@app.post("/location-risk", response_model=AnalyzeResponse)
def location_risk(payload: AnalyzeRequest) -> AnalyzeResponse:
    validate_coordinates(payload.lat, payload.lng)
    return build_analysis_response(payload)


@app.get("/risk")
def get_risk(
    lat: float = Query(..., description="Latitudine"),
    lng: float = Query(..., description="Longitudine"),
) -> dict[str, Any]:
    validate_coordinates(lat, lng)

    payload = AnalyzeRequest(lat=lat, lng=lng)
    result = build_analysis_response(payload)
    human = build_human_risk_payload(result)

    return {
        "risk_level": result.level,
        "level_label": result.level,
        "score": result.score,
        "score_text": human["score_text"],
        "message": result.message,
        "human_title": human["human_title"],
        "data_quality_label": human["data_quality_label"],
        "risk_reasons": human["risk_reasons"],
        "map_legend": human["map_legend"],
        "heatmap_note": human["heatmap_note"],
        "county": result.county,
        "city": result.city,
        "confidence": result.confidence,
        "confidence_percent": result.confidence_percent,
        "incidents_summary": model_to_dict(result.incidents_summary),
        "incidents_count": result.incidents_count,
        "serious_incidents_count": human["serious_incidents_count"],
        "sources_used": result.sources_used,
        "closest_severe_incident": model_to_dict(result.closest_severe_incident)
        if result.closest_severe_incident is not None
        else None,
        "analyzed_at": result.analyzed_at,
        "debug": result.debug,
    }


@app.get("/serious-incidents")
def serious_incidents(
    lat: float = Query(..., description="Latitudine centru"),
    lng: float = Query(..., description="Longitudine centru"),
    radius_m: int = Query(default=15000, ge=500, le=50000, description="Rază în metri"),
    lookback_days: int = Query(default=365, ge=1, le=365, description="Fereastră analiză"),
    limit: int = Query(default=20, ge=1, le=50, description="Număr maxim incidente"),
) -> dict[str, Any]:
    validate_coordinates(lat, lng)

    try:
        items = get_serious_incidents_for_location(
            center_lat=lat,
            center_lng=lng,
            radius_m=radius_m,
            lookback_days=lookback_days,
            limit=limit,
        )
    except Exception as exc:
        logger.exception("serious_incidents.failed lat=%s lng=%s error=%s", lat, lng, exc)
        raise HTTPException(status_code=500, detail=f"Eroare la încărcarea incidentelor grave: {exc}")

    return {
        "count": len(items),
        "radius_m": radius_m,
        "lookback_days": lookback_days,
        "title": "Incidente grave raportate și surse",
        "explanation": (
            "Această pagină afișează incidentele grave raportate în zona extinsă: "
            "omucidere, violență sexuală și tâlhărie. Fiecare incident este afișat "
            "cu sursa principală disponibilă."
        ),
        "legend": [
            "🚨 Incident grav",
            "✅ Confirmat oficial",
            "📰 Publicat în presă",
            "📍 Locație aproximativă",
        ],
        "items": items,
    }


@app.get("/heatmap")
def heatmap(
    lat: float = Query(..., description="Latitudine centru"),
    lng: float = Query(..., description="Longitudine centru"),
    radius_m: int = Query(default=10000, ge=200, le=20000, description="Rază în metri"),
    lookback_days: int = Query(default=365, ge=1, le=365, description="Fereastră analiză"),
) -> dict[str, Any]:
    validate_coordinates(lat, lng)

    try:
        points = get_heatmap_points(
            center_lat=lat,
            center_lng=lng,
            radius_m=radius_m,
            lookback_days=lookback_days,
        )
    except Exception as exc:
        logger.exception("heatmap.failed lat=%s lng=%s error=%s", lat, lng, exc)
        raise HTTPException(status_code=500, detail=f"Eroare la generarea heatmap: {exc}")

    return {
        "count": len(points),
        "geo_points_found": len(points),
        "radius_m": radius_m,
        "lookback_days": lookback_days,
        "mode": "real_geo_only",
        "explanation": (
            "Heatmap-ul indică zone aproximative de risc calculate din incidente geolocalizate. "
            "Nu reprezintă automat locul exact al unui incident."
        ),
        "points": points,
    }


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """
    <!DOCTYPE html>
    <html lang="ro">
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <title>Lazarus Safe</title>
    </head>
    <body style="font-family: Arial, sans-serif; padding: 24px;">
        <h1>Lazarus Safe API</h1>
        <p>API activ.</p>
        <ul>
            <li>POST /analyze</li>
            <li>POST /location-risk</li>
            <li>GET /risk</li>
            <li>GET /serious-incidents</li>
            <li>GET /heatmap</li>
            <li>GET /health</li>
            <li>GET /ready</li>
        </ul>
    </body>
    </html>
    """