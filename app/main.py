from typing import Optional

import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.db import (
    get_connection,
    get_db_path,
    initialize_database,
    list_tables,
    validate_critical_tables,
)
from app.risk_engine import evaluate_risk, get_sources_used
from app.schemas import AnalyzeRequest, AnalyzeResponse

import scripts.seed_area_profiles as seed_area_profiles_script
import scripts.seed_sources as seed_sources_script


app = FastAPI(
    title="Lazarus Safe API",
    version="2.1.0",
    description="API pentru evaluarea riscului de securitate fizică pe baza locației.",
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
    print("[startup] Initializing database...")
    initialize_database()
    validate_critical_tables()

    try:
        with get_connection() as conn:
            print(f"[startup] DB path: {get_db_path()}")
            print(f"[startup] Tables: {list_tables(conn)}")
    except Exception as exc:
        print(f"[startup] DB inspection error: {exc}")

    try:
        seed_sources_script.main()
        print("[startup] sources seeded")
    except Exception as exc:
        print(f"[startup] seed_sources error: {exc}")

    try:
        seed_area_profiles_script.main()
        print("[startup] area profiles seeded")
    except Exception as exc:
        print(f"[startup] seed_area_profiles error: {exc}")


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
    }

    return aliases.get(value, value)


def reverse_geocode_real(lat: float, lng: float) -> tuple[Optional[str], Optional[str]]:
    url = "https://nominatim.openstreetmap.org/reverse"
    headers = {
        "User-Agent": "LazarusSafeApp/2.1 (contact: lazardp@gmail.com)",
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
        response = requests.get(url, params=params, headers=headers, timeout=10)
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

        print(
            f"[geocode] lat={lat} lng={lng} "
            f"raw_county={raw_county} raw_city={raw_city} "
            f"county={county} city={city}"
        )

        if county:
            return county, city

    except Exception as exc:
        print(f"[geocode] error lat={lat} lng={lng}: {exc}")

    if 44.3 <= lat <= 44.6 and 25.9 <= lng <= 26.3:
        return "bucuresti", "bucuresti"

    if 44.7 <= lat <= 45.0 and 24.7 <= lng <= 25.1:
        return "arges", "pitesti"

    return None, None


def empty_incidents_summary() -> dict:
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


def build_analysis_response(payload: AnalyzeRequest) -> AnalyzeResponse:
    county, city = reverse_geocode_real(payload.lat, payload.lng)

    if not county:
        return AnalyzeResponse(
            level="UNKNOWN",
            message="Nu am putut identifica județul sau localitatea pentru coordonatele primite.",
            county=None,
            city=None,
            incidents_summary=empty_incidents_summary(),
            sources_used=[],
        )

    try:
        result = evaluate_risk(county, city)
        sources_used = get_sources_used(county, city)
    except Exception as exc:
        print(f"[risk_engine] county={county} city={city} error={exc}")
        return AnalyzeResponse(
            level="UNKNOWN",
            message="Locația a fost identificată, dar analiza de risc a eșuat.",
            county=county,
            city=city,
            incidents_summary=empty_incidents_summary(),
            sources_used=[],
        )

    if not isinstance(result, dict):
        return AnalyzeResponse(
            level="UNKNOWN",
            message="Analiza nu a returnat un rezultat valid.",
            county=county,
            city=city,
            incidents_summary=empty_incidents_summary(),
            sources_used=[],
        )

    return AnalyzeResponse(
        level=result.get("level", "UNKNOWN"),
        message=result.get("message", "Analiza nu a putut fi completată."),
        county=county,
        city=city,
        incidents_summary=result.get("incidents_summary", empty_incidents_summary()),
        sources_used=sources_used if isinstance(sources_used, list) else [],
    )


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """
    <html>
        <head>
            <title>Lazarus Safe API</title>
        </head>
        <body style="font-family: Arial, sans-serif; background:#0b1736; color:white; padding:40px;">
            <div style="max-width:760px;margin:auto;background:#142554;padding:24px;border-radius:16px;">
                <h1>Lazarus Safe API</h1>
                <p>Evaluator de risc la securitate fizică</p>
                <p><strong>Endpoint principal:</strong> <code>POST /analyze</code></p>
                <p><strong>Endpoint alternativ:</strong> <code>POST /location-risk</code></p>
                <p><strong>Documentație:</strong> <code>/docs</code></p>
                <p><strong>Health:</strong> <code>/health</code></p>
                <p><strong>Debug DB:</strong> <code>/debug/db</code></p>
            </div>
        </body>
    </html>
    """


@app.get("/debug/db")
def debug_db() -> dict:
    return {
        "db_path": get_db_path(),
        "tables": list_tables(),
    }


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "Lazarus Safe API",
    }


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    return build_analysis_response(payload)


@app.post("/location-risk", response_model=AnalyzeResponse)
def location_risk(payload: AnalyzeRequest) -> AnalyzeResponse:
    return build_analysis_response(payload)