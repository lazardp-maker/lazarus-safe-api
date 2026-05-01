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
APP_VERSION = os.getenv("APP_VERSION", "3.5.2")
APP_ENV = os.getenv("APP_ENV", "development")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
GEOCODER_TIMEOUT_SECONDS = int(os.getenv("GEOCODER_TIMEOUT_SECONDS", "10"))

logger = logging.getLogger(APP_NAME)
logging.basicConfig(level=LOG_LEVEL)

app = FastAPI(title=APP_NAME, version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# INIT
# -----------------------------
@app.on_event("startup")
def startup_event():
    initialize_database()
    validate_critical_tables()


# -----------------------------
# UTILS
# -----------------------------
def validate_coordinates(lat: float, lng: float):
    if not (-90 <= lat <= 90):
        raise HTTPException(422, "Lat invalid")
    if not (-180 <= lng <= 180):
        raise HTTPException(422, "Lng invalid")


def reverse_geocode_real(lat: float, lng: float):
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lng, "format": "jsonv2"},
            headers={"User-Agent": "LazarusSafe"},
            timeout=10,
        )
        data = r.json()
        addr = data.get("address", {})
        return addr.get("county"), addr.get("city") or addr.get("town")
    except:
        return None, None


def model_to_dict(v):
    if hasattr(v, "model_dump"):
        return v.model_dump()
    if hasattr(v, "dict"):
        return v.dict()
    return v if isinstance(v, dict) else {}


# -----------------------------
# 🔥 FIX IMPORTANT
# -----------------------------
def build_serious_incident_from_row(row: Any) -> dict[str, Any]:
    item = dict(row)

    labels = {
        "homicide": "omor / omucidere",
        "sexual_violence": "violență sexuală",
        "robbery": "tâlhărie",
    }

    city = item.get("city")
    county = item.get("county")

    if not city and county:
        city = f"necunoscut ({county})"

    source_url = (
        item.get("source_url")
        or item.get("url")
        or item.get("article_url")
    )

    source_name = item.get("source_name") or item.get("source") or "necunoscut"

    return {
        "incident_id": item.get("id"),
        "incident_type": item.get("incident_type"),
        "incident_label": labels.get(item.get("incident_type"), "incident grav"),
        "title": item.get("title"),
        "summary": item.get("summary"),
        "city": city,
        "county": county,
        "latitude": item.get("latitude"),
        "longitude": item.get("longitude"),
        "distance_text": "locație aproximativă",
        "days_ago": item.get("days_ago"),
        "published_date": item.get("published_date"),
        "source_name": source_name,
        "source_url": source_url,
        "source_title": item.get("title"),
        "official_confirmation": bool(item.get("is_verified") == 1),
        "verification_label": "OFICIAL" if item.get("is_verified") == 1 else "SURSA PRESĂ",
    }


# -----------------------------
# ANALYZE
# -----------------------------
def build_analysis_response(payload: AnalyzeRequest):
    county, city = reverse_geocode_real(payload.lat, payload.lng)

    result = evaluate_risk(
        county=county,
        city=city,
        user_lat=payload.lat,
        user_lng=payload.lng,
    )

    return AnalyzeResponse(
        level=result.get("level"),
        score=result.get("score_internal"),
        message=result.get("message"),
        county=county,
        city=city,
        incidents_summary=result.get("incidents_summary"),
        incidents_count=sum(result.get("incidents_summary", {}).values()),
        sources_used=get_sources_used(county, city),
        confidence=result.get("confidence"),
        confidence_percent=result.get("confidence") * 100,
        closest_severe_incident=result.get("closest_severe_incident"),
        analyzed_at=datetime.now(timezone.utc).isoformat(),
    )


# -----------------------------
# ROUTES
# -----------------------------
@app.get("/risk")
def risk(lat: float, lng: float):
    payload = AnalyzeRequest(lat=lat, lng=lng)
    result = build_analysis_response(payload)
    human = user_friendly_explanation(
        level=result.level,
        score=result.score,
        confidence=result.confidence,
        incidents_count=result.incidents_count,
        severe_count=0,
        closest_severe=None,
        lookback_days=60,
    )

    return {
        "score": result.score,
        "message": result.message,
        "county": result.county,
        "city": result.city,
        "incidents_summary": model_to_dict(result.incidents_summary),
        "sources_used": result.sources_used,
        "confidence_percent": result.confidence_percent,
        "score_text": human.get("score_text"),
    }


@app.get("/serious-incidents")
def serious_incidents(lat: float, lng: float):
    items = get_serious_incidents_for_location(lat, lng, 15000, 365, 20)

    if not items:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM incidents WHERE incident_type IN ('homicide','sexual_violence','robbery') LIMIT 20"
            ).fetchall()
            items = [build_serious_incident_from_row(r) for r in rows]

    return {"items": items}


@app.get("/heatmap")
def heatmap(lat: float, lng: float):
    return {"points": get_heatmap_points(lat, lng, 10000, 365)}


@app.get("/")
def home():
    return {"status": "ok"}
from math import radians, sin, cos, sqrt, atan2

def haversine_meters(lat1, lon1, lat2, lon2):
    R = 6371000
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)

    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c


@app.get("/serious-incidents")
def get_serious_incidents(lat: float, lng: float, radius_m: int = 15000, lookback_days: int = 120):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM incidents
        WHERE incident_type IN ('homicide', 'sexual_violence', 'robbery')
    """)

    rows = cursor.fetchall()
    results = []

    for row in rows:
        if row["latitude"] is None or row["longitude"] is None:
            continue

        distance = haversine_meters(lat, lng, row["latitude"], row["longitude"])

        if distance > radius_m:
            continue

        if row.get("days_ago") is not None and row["days_ago"] > lookback_days:
            continue

        results.append({
            "incident_id": row["incident_uid"],
            "incident_type": row["incident_type"],
            "incident_label": row["incident_type"].replace("_", " "),

            "city": row["city"],
            "county": row["county"],

            "latitude": row["latitude"],
            "longitude": row["longitude"],

            "distance_m": distance,
            "distance_text": f"{round(distance/1000,1)} km",

            "days_ago": row["days_ago"],
            "published_date": row["published_date"],

            # 🔴 IMPORTANT
            "source_name": row.get("source_name"),
            "source_url": row.get("source_url"),
            "source_title": row.get("title"),

            "official_confirmation": row.get("verification_status") == "verified",
            "verification_label": "OFICIAL" if row.get("verification_status") == "verified" else "SURSA"
        })

    conn.close()

    return {
        "count": len(results),
        "items": results
    }