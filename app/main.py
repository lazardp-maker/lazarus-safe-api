from typing import Optional

import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from scripts.init_db import initialize_database
import scripts.seed_sources as seed_sources_script
import scripts.seed_area_profiles as seed_area_profiles_script

from app.schemas import AnalyzeRequest, AnalyzeResponse
from app.risk_engine import evaluate_risk, get_sources_used


app = FastAPI(
    title="Lazarus Safe API",
    version="2.0.0",
    description="API pentru evaluarea riscului de securitate fizică pe baza locației."
)


@app.on_event("startup")
def startup_event() -> None:
    print("🚀 Initializing database...")
    initialize_database()

    try:
        seed_sources_script.main()
        print("✅ sources seeded")
    except Exception as e:
        print(f"seed_sources error: {e}")

    try:
        seed_area_profiles_script.main()
        print("✅ area profiles seeded")
    except Exception as e:
        print(f"seed_area_profiles error: {e}")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

    value = " ".join(value.split())
    return value


def reverse_geocode_real(lat: float, lng: float) -> tuple[Optional[str], Optional[str]]:
    url = "https://nominatim.openstreetmap.org/reverse"

    headers = {
        "User-Agent": "LazarusSafe/1.0 (contact: lazardp@gmail.com)",
        "Accept": "application/json",
        "Accept-Language": "ro,en",
    }

    params = {
        "lat": lat,
        "lon": lng,
        "format": "jsonv2",
        "addressdetails": 1,
        "zoom": 14,
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        print(f"[geocode] status_code={response.status_code}")
        print(f"[geocode] raw_response={response.text[:1000]}")
        response.raise_for_status()

        data = response.json()
        address = data.get("address", {})

        county = (
            address.get("county")
            or address.get("state_district")
            or address.get("state")
        )

        city = (
            address.get("city")
            or address.get("town")
            or address.get("municipality")
            or address.get("village")
            or address.get("hamlet")
            or address.get("suburb")
            or address.get("city_district")
        )

        county_n = normalize_text(county)
        city_n = normalize_text(city)

        if county_n in {"municipiul bucuresti", "bucharest"}:
            county_n = "bucuresti"

        if city_n in {"municipiul bucuresti", "bucharest"}:
            city_n = "bucuresti"

        print(f"[geocode] county={county} -> {county_n}")
        print(f"[geocode] city={city} -> {city_n}")

        return county_n, city_n

    except Exception as e:
        print(f"[geocode] error={e}")
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

    result = evaluate_risk(county, city)
    sources_used = get_sources_used(county)

    return AnalyzeResponse(
        level=result["level"],
        message=result["message"],
        county=county,
        city=city,
        incidents_summary=result["incidents_summary"],
        sources_used=sources_used,
    )


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return """
    <html>
        <head>
            <title>Lazarus Safe API</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    background: #0b1736;
                    color: white;
                    padding: 40px;
                }
                .box {
                    max-width: 760px;
                    margin: auto;
                    background: #142554;
                    padding: 24px;
                    border-radius: 16px;
                    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
                }
                code {
                    color: #ffd27d;
                    font-size: 16px;
                }
                h1 {
                    margin-top: 0;
                }
                p {
                    line-height: 1.6;
                }
            </style>
        </head>
        <body>
            <div class="box">
                <h1>Lazarus Safe API</h1>
                <p>Evaluator de risc la securitate fizică - Lazar Vasile</p>
                <p><strong>Endpoint principal:</strong></p>
                <p><code>POST /analyze</code></p>
                <p><strong>Endpoint alternativ:</strong></p>
                <p><code>POST /location-risk</code></p>
                <p><strong>Documentație Swagger:</strong></p>
                <p><code>/docs</code></p>
            </div>
        </body>
    </html>
    """


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