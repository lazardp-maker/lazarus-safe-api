from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from scripts.init_db import initialize_database
from app.schemas import AnalyzeRequest, AnalyzeResponse
from app.risk_engine import evaluate_risk, get_sources_used


initialize_database()

app = FastAPI(
    title="Lazarus Safe API",
    version="2.0.0",
    description="API pentru evaluarea riscului de securitate fizică pe baza locației."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def reverse_geocode_mock(lat: float, lng: float) -> tuple[Optional[str], Optional[str]]:
    """
    Variantă temporară pentru MVP.
    Se va înlocui ulterior cu geocodare reală.
    """
    if 44.7 <= lat <= 45.0 and 24.7 <= lng <= 25.1:
        return "arges", "pitesti"

    if 44.3 <= lat <= 44.6 and 25.9 <= lng <= 26.3:
        return "bucuresti", "bucuresti"

    return None, None


def build_analysis_response(payload: AnalyzeRequest) -> AnalyzeResponse:
    county, city = reverse_geocode_mock(payload.lat, payload.lng)
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
        "service": "Lazarus Safe API"
    }


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest) -> AnalyzeResponse:
    return build_analysis_response(payload)


@app.post("/location-risk", response_model=AnalyzeResponse)
def location_risk(payload: AnalyzeRequest) -> AnalyzeResponse:
    return build_analysis_response(payload)
