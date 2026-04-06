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
)
from app.schemas import AnalyzeRequest, AnalyzeResponse

APP_NAME = "Lazarus Safe API"
APP_VERSION = os.getenv("APP_VERSION", "3.3.1")
APP_ENV = os.getenv("APP_ENV", "development")
GEOCODER_TIMEOUT_SECONDS = int(os.getenv("GEOCODER_TIMEOUT_SECONDS", "10"))

logger = logging.getLogger(APP_NAME)
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=(
        "API pentru evaluarea riscului de securitate fizică pe baza locației, "
        "cu suport pentru analiză geospațială și colectare de date publice."
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
    """
    Startup minimalist și sigur:
    - inițializează baza de date
    - validează tabelele critice
    - loghează informații utile
    NU rulează scraping, seed sau alte joburi grele.
    """
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
        "county of ",
        "county ",
    ]

    for prefix in prefixes:
        if value.startswith(prefix):
            value = value[len(prefix):].strip()

    aliases = {
        "bucharest": "bucuresti",
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


def reverse_geocode_real(lat: float, lng: float) -> tuple[Optional[str], Optional[str]]:
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
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=GEOCODER_TIMEOUT_SECONDS,
        )
        response.raise_for_status()

        data = response.json()
        address = data.get("address", {})

        raw_county = (
            address.get("county")
            or address.get("state_district")
            or address.get("state")
        )

        raw_city = (
            address.get("city")
            or address.get("municipality")
            or address.get("town")
            or address.get("village")
            or address.get("suburb")
            or address.get("city_district")
        )

        county = canonicalize_place(raw_county)
        city = canonicalize_place(raw_city)

        if county == "bucuresti":
            city = "bucuresti"

        logger.info(
            "reverse_geocode.success lat=%s lng=%s raw_county=%s raw_city=%s county=%s city=%s",
            lat,
            lng,
            raw_county,
            raw_city,
            county,
            city,
        )

        if county:
            return county, city

    except Exception as exc:
        logger.warning(
            "reverse_geocode.failed lat=%s lng=%s error=%s",
            lat,
            lng,
            exc,
        )

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


def incidents_summary_to_dict(value: Any) -> dict[str, int]:
    if value is None:
        return empty_incidents_summary()

    if isinstance(value, dict):
        summary = value.copy()
    elif hasattr(value, "dict"):
        summary = value.dict()
    elif hasattr(value, "model_dump"):
        summary = value.model_dump()
    else:
        return empty_incidents_summary()

    default_summary = empty_incidents_summary()
    default_summary.update(summary)
    return default_summary


def build_analysis_response(payload: AnalyzeRequest) -> AnalyzeResponse:
    analyzed_at = datetime.now(timezone.utc).isoformat()

    county, city = reverse_geocode_real(payload.lat, payload.lng)

    if not county:
        return AnalyzeResponse(
            level="UNKNOWN",
            message="Nu am putut identifica județul sau localitatea pentru coordonatele primite.",
            county=None,
            city=None,
            incidents_summary=empty_incidents_summary(),
            sources_used=[],
            confidence=0.0,
            analyzed_at=analyzed_at,
            debug={
                "reason": "reverse_geocode_failed",
                "input_lat": payload.lat,
                "input_lng": payload.lng,
            },
        )

    try:
        result = evaluate_risk(
            county=county,
            city=city,
            user_lat=payload.lat,
            user_lng=payload.lng,
        )
        sources_used = get_sources_used(county, city)
    except Exception as exc:
        logger.exception(
            "risk_engine.failed county=%s city=%s error=%s",
            county,
            city,
            exc,
        )
        return AnalyzeResponse(
            level="UNKNOWN",
            message="Locația a fost identificată, dar analiza de risc a eșuat.",
            county=county,
            city=city,
            incidents_summary=empty_incidents_summary(),
            sources_used=[],
            confidence=0.0,
            analyzed_at=analyzed_at,
            debug={
                "reason": "risk_engine_failed",
                "error": str(exc),
                "county": county,
                "city": city,
            },
        )

    if not isinstance(result, dict):
        logger.warning(
            "risk_engine.invalid_result_type county=%s city=%s type=%s",
            county,
            city,
            type(result).__name__,
        )
        return AnalyzeResponse(
            level="UNKNOWN",
            message="Analiza nu a returnat un rezultat valid.",
            county=county,
            city=city,
            incidents_summary=empty_incidents_summary(),
            sources_used=[],
            confidence=0.0,
            analyzed_at=analyzed_at,
            debug={
                "reason": "invalid_risk_result",
                "county": county,
                "city": city,
            },
        )

    return AnalyzeResponse(
        level=result.get("level", "UNKNOWN"),
        message=result.get("message", "Analiza nu a putut fi completată."),
        county=county,
        city=city,
        incidents_summary=incidents_summary_to_dict(
            result.get("incidents_summary", empty_incidents_summary())
        ),
        sources_used=sources_used if isinstance(sources_used, list) else [],
        confidence=result.get("confidence", 0.0),
        analyzed_at=analyzed_at,
        debug=result.get("meta"),
    )


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
            "articles": articles_total,
        },
    }


@app.get("/ready")
def ready() -> dict[str, Any]:
    try:
        with get_connection() as conn:
            tables = list_tables(conn)

        required_tables = {
            "sources",
            "area_risk_profiles",
            "incidents",
            "articles",
        }
        missing_tables = sorted(required_tables - set(tables))

        return {
            "status": "ok" if not missing_tables else "degraded",
            "service": APP_NAME,
            "version": APP_VERSION,
            "missing_tables": missing_tables,
        }
    except Exception as exc:
        logger.exception("ready.failed error=%s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Readiness check failed: {exc}",
        )


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

        return {
            "db_path": get_db_path(),
            "tables": tables,
            "columns": columns,
        }


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

        cursor.execute(
            """
            SELECT verification_status, COUNT(*) AS total
            FROM incidents
            GROUP BY verification_status
            ORDER BY total DESC
            """
        )
        by_verification = [
            {"verification_status": row["verification_status"], "total": row["total"]}
            for row in cursor.fetchall()
        ]

        cursor.execute(
            """
            SELECT incident_type, COUNT(*) AS total
            FROM incidents
            GROUP BY incident_type
            ORDER BY total DESC
            """
        )
        by_type = [
            {"incident_type": row["incident_type"], "total": row["total"]}
            for row in cursor.fetchall()
        ]

    return {
        "db_path": get_db_path(),
        "totals": {
            "sources": sources_total,
            "articles": articles_total,
            "incidents": incidents_total,
            "incident_mentions": mentions_total,
            "area_risk_profiles": profiles_total,
        },
        "incidents_by_verification_status": by_verification,
        "incidents_by_type": by_type,
    }


@app.get("/admin/recent-incidents")
def admin_recent_incidents(
    limit: int = Query(default=20, ge=1, le=100),
    county: Optional[str] = Query(default=None),
    city: Optional[str] = Query(default=None),
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

    where_sql = " AND ".join(where_parts)

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
            ai_confidence,
            is_verified,
            verification_status,
            source_priority,
            created_at
        FROM incidents
        WHERE {where_sql}
        ORDER BY
            COALESCE(date(event_date), date(published_date), date(created_at)) DESC,
            id DESC
        LIMIT ?
    """
    params.append(limit)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

    incidents = []
    for row in rows:
        incidents.append(
            {
                "id": row["id"],
                "incident_uid": row["incident_uid"],
                "incident_type": row["incident_type"],
                "severity_level": row["severity_level"],
                "title": row["title"],
                "summary": row["summary"],
                "event_date": row["event_date"],
                "published_date": row["published_date"],
                "days_ago": row["days_ago"],
                "city": row["city"],
                "county": row["county"],
                "ai_confidence": row["ai_confidence"],
                "is_verified": row["is_verified"],
                "verification_status": row["verification_status"],
                "source_priority": row["source_priority"],
                "created_at": row["created_at"],
            }
        )

    return {
        "count": len(incidents),
        "filters": {
            "county": county_n,
            "city": city_n,
            "limit": limit,
        },
        "items": incidents,
    }


@app.post("/admin/run-collector")
def admin_run_collector() -> dict[str, str]:
    """
    Rulează collectorul manual, la cerere.
    Importul collectorului este lazy și se face doar când endpoint-ul este apelat.
    """
    try:
        logger.info("collector.manual_run.begin")
        from app.collectors.collector_real import main as run_collector

        run_collector()
        logger.info("collector.manual_run.complete")
        return {
            "status": "ok",
            "message": "Collectorul a rulat cu succes.",
        }
    except Exception as exc:
        logger.exception("collector.manual_run.failed error=%s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"Eroare la rularea collectorului: {exc}",
        )


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    return build_analysis_response(payload)


@app.post("/location-risk", response_model=AnalyzeResponse)
def location_risk(payload: AnalyzeRequest) -> AnalyzeResponse:
    return build_analysis_response(payload)


@app.get("/risk")
def get_risk(
    lat: float = Query(..., description="Latitudine"),
    lng: float = Query(..., description="Longitudine"),
) -> dict[str, Any]:
    payload = AnalyzeRequest(lat=lat, lng=lng)
    result = build_analysis_response(payload)

    summary_dict = incidents_summary_to_dict(result.incidents_summary)
    total_incidents = sum(
        int(v) for v in summary_dict.values() if isinstance(v, (int, float))
    )

    confidence_raw = float(result.confidence) if result.confidence is not None else 0.0
    confidence_percent = round(confidence_raw * 100.0, 1)

    return {
        "risk_level": result.level,
        "message": result.message,
        "county": result.county,
        "city": result.city,
        "confidence": confidence_raw,
        "confidence_percent": confidence_percent,
        "incidents_summary": summary_dict,
        "incidents_count": total_incidents,
        "sources_used": result.sources_used,
        "analyzed_at": result.analyzed_at,
        "debug": result.debug,
    }


@app.get("/heatmap")
def heatmap(
    lat: float = Query(..., description="Latitudine centru"),
    lng: float = Query(..., description="Longitudine centru"),
    radius_m: int = Query(default=10000, ge=200, le=20000, description="Rază în metri"),
    lookback_days: int = Query(default=365, ge=1, le=365, description="Fereastră analiză"),
) -> dict[str, Any]:
    try:
        points = get_heatmap_points(
            center_lat=lat,
            center_lng=lng,
            radius_m=radius_m,
            lookback_days=lookback_days,
        )
    except Exception as exc:
        logger.exception(
            "heatmap.failed lat=%s lng=%s radius_m=%s lookback_days=%s error=%s",
            lat,
            lng,
            radius_m,
            lookback_days,
            exc,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Eroare la generarea heatmap: {exc}",
        )

    return {
        "count": len(points),
        "geo_points_found": len(points),
        "radius_m": radius_m,
        "lookback_days": lookback_days,
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

        <link
            rel="stylesheet"
            href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
            integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
            crossorigin=""
        />

        <style>
            * {
                box-sizing: border-box;
            }

            body {
                margin: 0;
                font-family: Arial, sans-serif;
                background: #08142f;
                color: white;
            }

            #map {
                height: 100vh;
                width: 100%;
            }

            .panel {
                position: absolute;
                top: 20px;
                left: 20px;
                z-index: 1000;
                width: 395px;
                max-width: calc(100% - 40px);
                background: rgba(15, 31, 74, 0.96);
                border-radius: 18px;
                padding: 18px;
                box-shadow: 0 12px 32px rgba(0, 0, 0, 0.35);
                border: 1px solid rgba(255,255,255,0.08);
            }

            .brand {
                margin: 0 0 6px 0;
                font-size: 24px;
                font-weight: 700;
                letter-spacing: 0.3px;
            }

            .subtitle {
                margin: 0 0 14px 0;
                color: #d7e4ff;
                font-size: 14px;
                line-height: 1.45;
            }

            .actions {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-bottom: 12px;
            }

            button {
                flex: 1 1 110px;
                padding: 11px 12px;
                border: none;
                border-radius: 10px;
                cursor: pointer;
                font-size: 14px;
                font-weight: bold;
                transition: 0.2s ease;
            }

            button:hover {
                transform: translateY(-1px);
            }

            .btn-primary {
                background: #ffffff;
                color: #0b1736;
            }

            .btn-secondary {
                background: #1f3776;
                color: #ffffff;
                border: 1px solid rgba(255,255,255,0.12);
            }

            .btn-ghost {
                background: #162a60;
                color: #ffffff;
                border: 1px solid rgba(255,255,255,0.08);
            }

            .status {
                margin-top: 6px;
                padding: 14px;
                border-radius: 12px;
                background: rgba(255,255,255,0.06);
                font-size: 14px;
                line-height: 1.5;
                max-height: 62vh;
                overflow: auto;
            }

            .risk-badge {
                display: inline-block;
                margin-top: 8px;
                padding: 6px 10px;
                border-radius: 999px;
                font-size: 12px;
                font-weight: bold;
                letter-spacing: 0.3px;
            }

            .risk-low {
                background: rgba(46, 204, 113, 0.18);
                color: #7CFFB2;
            }

            .risk-medium {
                background: rgba(241, 196, 15, 0.18);
                color: #FFD95B;
            }

            .risk-high {
                background: rgba(231, 76, 60, 0.18);
                color: #FF8E82;
            }

            .risk-unknown {
                background: rgba(255,255,255,0.12);
                color: #ECECEC;
            }

            .muted {
                color: #b7c8ef;
                font-size: 13px;
            }

            .small-title {
                margin-top: 10px;
                margin-bottom: 6px;
                font-size: 13px;
                font-weight: bold;
                color: #ffffff;
            }

            .small-list {
                margin: 8px 0 0 18px;
                padding: 0;
                color: #e5ecff;
                font-size: 13px;
            }

            .footer-note {
                margin-top: 10px;
                font-size: 12px;
                color: #9fb1e8;
            }

            code {
                background: rgba(255,255,255,0.08);
                padding: 2px 6px;
                border-radius: 6px;
                font-size: 12px;
            }

            @media (max-width: 768px) {
                .panel {
                    top: 12px;
                    left: 12px;
                    right: 12px;
                    width: auto;
                    max-width: none;
                }

                .actions {
                    flex-direction: column;
                }
            }
        </style>
    </head>
    <body>
        <div id="map"></div>

        <div class="panel">
            <h1 class="brand">Lazarus Safe</h1>
            <p class="subtitle">
                Evaluare rapidă a riscului de securitate fizică pe baza locației și a incidentelor relevante.
            </p>

            <div class="actions">
                <button class="btn-primary" onclick="checkRisk()">Verifică zona</button>
                <button class="btn-secondary" onclick="useMyLocation()">Locația mea</button>
                <button class="btn-ghost" onclick="toggleHeatmap()">Arată / Ascunde heatmap</button>
            </div>

            <div id="result" class="status">
                Selectează o locație pe hartă sau apasă pe <strong>Locația mea</strong>.
            </div>

            <div class="footer-note">
                API: <code>GET /risk</code> și <code>GET /heatmap</code>
            </div>
        </div>

        <script
            src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
            integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
            crossorigin=""
        ></script>
        <script src="https://unpkg.com/leaflet.heat/dist/leaflet-heat.js"></script>

        <script>
            const map = L.map("map").setView([44.4268, 26.1025], 13);

            L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
                maxZoom: 19,
                attribution: "&copy; OpenStreetMap contributors"
            }).addTo(map);

            let marker = null;
            let selectedLat = null;
            let selectedLng = null;
            let heatLayer = null;
            let heatCircles = [];
            let heatmapVisible = false;

            function setMarker(lat, lng) {
                selectedLat = lat;
                selectedLng = lng;

                if (marker) {
                    map.removeLayer(marker);
                }

                marker = L.marker([lat, lng]).addTo(map);
                map.setView([lat, lng], 15);
            }

            function clearHeatmapLayers() {
                if (heatLayer) {
                    map.removeLayer(heatLayer);
                    heatLayer = null;
                }

                if (heatCircles.length) {
                    heatCircles.forEach(layer => {
                        try {
                            map.removeLayer(layer);
                        } catch (e) {}
                    });
                    heatCircles = [];
                }
            }

            function getCircleColor(intensity) {
                if (intensity >= 0.85) return "#ff0000";
                if (intensity >= 0.65) return "#ff7a00";
                if (intensity >= 0.45) return "#ffd400";
                if (intensity >= 0.25) return "#7dff00";
                return "#00a3ff";
            }

            function drawCircleFallback(points) {
                clearHeatmapLayers();

                heatCircles = points.map((p) => {
                    const intensity = Math.max(Number(p.intensity || 0.25), 0.20);
                    const radius = 120 + (intensity * 260);

                    return L.circle([Number(p.lat), Number(p.lng)], {
                        radius: radius,
                        color: getCircleColor(intensity),
                        fillColor: getCircleColor(intensity),
                        fillOpacity: Math.min(0.18 + intensity * 0.35, 0.55),
                        weight: 1
                    }).addTo(map);
                });
            }

            map.on("click", function (e) {
                setMarker(e.latlng.lat, e.latlng.lng);
                document.getElementById("result").innerHTML = `
                    <div><strong>Locație selectată</strong></div>
                    <div class="muted">Lat: ${e.latlng.lat.toFixed(6)}, Lng: ${e.latlng.lng.toFixed(6)}</div>
                    <div class="footer-note">Apasă pe „Verifică zona”.</div>
                `;
            });

            function getRiskClass(level) {
                const value = (level || "").toUpperCase();

                if (
                    value.includes("LOW") ||
                    value.includes("SAFE") ||
                    value.includes("SCAZUT") ||
                    value.includes("STABILA")
                ) {
                    return "risk-low";
                }

                if (
                    value.includes("MED") ||
                    value.includes("MODERAT") ||
                    value === "PRUDENȚĂ" ||
                    value === "PRUDENTA"
                ) {
                    return "risk-medium";
                }

                if (
                    value.includes("HIGH") ||
                    value.includes("RIDICAT") ||
                    value.includes("SEVER") ||
                    value.includes("SERIOASA")
                ) {
                    return "risk-high";
                }

                return "risk-unknown";
            }

            function buildIncidentsList(summary) {
                if (!summary || typeof summary !== "object") {
                    return "<div class='muted'>Fără sumar incidente.</div>";
                }

                const labels = {
                    homicide: "Omor",
                    sexual_violence: "Violență sexuală",
                    robbery: "Tâlhărie",
                    theft: "Furt",
                    violence: "Violență",
                    traffic: "Trafic",
                    emergency: "Urgențe",
                    public_order: "Ordine publică",
                    general: "General"
                };

                const items = Object.entries(summary)
                    .filter(([_, value]) => Number(value) > 0)
                    .map(([key, value]) => `<li>${labels[key] || key}: ${value}</li>`);

                if (!items.length) {
                    return "<div class='muted'>Nu au fost identificate incidente relevante în sumar.</div>";
                }

                return `<ul class="small-list">${items.join("")}</ul>`;
            }

            async function checkRisk() {
                if (selectedLat === null || selectedLng === null) {
                    alert("Selectează mai întâi o locație.");
                    return;
                }

                const resultBox = document.getElementById("result");
                resultBox.innerHTML = "Se analizează locația...";

                try {
                    const response = await fetch(`/risk?lat=${selectedLat}&lng=${selectedLng}`);

                    if (!response.ok) {
                        throw new Error(`HTTP ${response.status}`);
                    }

                    const data = await response.json();
                    const riskClass = getRiskClass(data.risk_level);

                    resultBox.innerHTML = `
                        <div>
                            <strong>${data.city || "Localitate necunoscută"}</strong>
                            ${data.county ? `, ${data.county}` : ""}
                        </div>

                        <div class="risk-badge ${riskClass}">
                            Risc: ${data.risk_level || "UNKNOWN"}
                        </div>

                        <p style="margin-top:10px; margin-bottom:6px;">
                            ${data.message || "Nu există mesaj disponibil."}
                        </p>

                        <div class="muted">
                            Confidence: ${Number(data.confidence_percent || 0).toFixed(1)}%
                        </div>

                        <div class="muted">
                            Incidente totale: ${data.incidents_count || 0}
                        </div>

                        <div class="small-title">Sumar incidente:</div>
                        ${buildIncidentsList(data.incidents_summary)}

                        <div class="footer-note">
                            Analizat la: ${data.analyzed_at || "-"}
                        </div>
                    `;

                    if (heatmapVisible) {
                        await loadHeatmap();
                    }
                } catch (error) {
                    resultBox.innerHTML = `
                        <div><strong>Eroare la analiză</strong></div>
                        <div class="muted">${error.message}</div>
                    `;
                }
            }

            async function loadHeatmap() {
                if (selectedLat === null || selectedLng === null) {
                    alert("Selectează mai întâi o locație.");
                    return;
                }

                const response = await fetch(
                    `/heatmap?lat=${selectedLat}&lng=${selectedLng}&radius_m=10000&lookback_days=365`
                );

                if (!response.ok) {
                    throw new Error(`Heatmap HTTP ${response.status}`);
                }

                const data = await response.json();
                console.log("HEATMAP RESPONSE:", data);

                clearHeatmapLayers();

                if (!data.points || !data.points.length) {
                    alert("Nu există puncte pentru heatmap.");
                    return;
                }

                const heatData = data.points.map((p) => [
                    Number(p.lat),
                    Number(p.lng),
                    Math.max(Number(p.intensity || 0.2) * 5, 0.35)
                ]);

                if (typeof L.heatLayer === "function") {
                    try {
                        heatLayer = L.heatLayer(heatData, {
                            radius: 55,
                            blur: 38,
                            maxZoom: 17,
                            minOpacity: 0.40,
                            max: 1.0,
                            gradient: {
                                0.20: "#00a3ff",
                                0.40: "#7dff00",
                                0.60: "#ffd400",
                                0.80: "#ff7a00",
                                1.00: "#ff0000"
                            }
                        }).addTo(map);
                        return;
                    } catch (err) {
                        console.error("heatLayer failed, fallback to circles", err);
                    }
                }

                drawCircleFallback(data.points);
            }

            async function toggleHeatmap() {
                if (selectedLat === null || selectedLng === null) {
                    alert("Selectează mai întâi o locație.");
                    return;
                }

                heatmapVisible = !heatmapVisible;

                if (!heatmapVisible) {
                    clearHeatmapLayers();
                    return;
                }

                try {
                    await loadHeatmap();
                } catch (error) {
                    console.error(error);
                    drawCircleFallback([
                        { lat: selectedLat, lng: selectedLng, intensity: 0.8 }
                    ]);
                }
            }

            function useMyLocation() {
                if (!navigator.geolocation) {
                    alert("Browserul nu suportă geolocația.");
                    return;
                }

                navigator.geolocation.getCurrentPosition(
                    function (position) {
                        const lat = position.coords.latitude;
                        const lng = position.coords.longitude;

                        setMarker(lat, lng);

                        document.getElementById("result").innerHTML = `
                            <div><strong>Locația ta a fost detectată</strong></div>
                            <div class="muted">Lat: ${lat.toFixed(6)}, Lng: ${lng.toFixed(6)}</div>
                            <div class="footer-note">Apasă pe „Verifică zona”.</div>
                        `;
                    },
                    function (error) {
                        document.getElementById("result").innerHTML = `
                            <div><strong>Nu am putut obține locația</strong></div>
                            <div class="muted">${error.message}</div>
                        `;
                    },
                    {
                        enableHighAccuracy: true,
                        timeout: 10000,
                        maximumAge: 0
                    }
                );
            }
        </script>
    </body>
    </html>
    """