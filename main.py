from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from scripts.init_db import initialize_database
import scripts.seed_area_profiles as seed_area_profiles_script
import scripts.seed_sources as seed_sources_script

from app.schemas import AnalyzeRequest, AnalyzeResponse
from app.risk_engine import evaluate_risk, get_sources_used


initialize_database()

try:
    seed_area_profiles_script.main()
except Exception as e:
    print(f"seed_area_profiles skipped: {e}")

try:
    seed_sources_script.main()
except Exception as e:
    print(f"seed_sources skipped: {e}")


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
    O înlocuim ulterior cu geocodare reală.
    """
    if 44.7 <= lat <= 45.0 and 24.7 <= lng <= 25.1:
        return "arges", "pitesti"

    if 44.3 <= lat <= 44.6 and 25.9 <= lng <= 26.3:
        return "bucuresti", "bucuresti"

    return None, None


@app.get("/", response_class=HTMLResponse)
def home():
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
                }
                code {
                    color: #ffd27d;
                    font-size: 16px;
                }
                h1 {
                    margin-top: 0;
                }
            </style>
        </head>
        <body>
            <div class="box">
                <h1>Lazarus Safe API</h1>
                <p>Evaluator de risc la securitate fizică - Lazar Vasile</p>
                <p>Endpoint principal:</p>
                <p><code>POST /analyze</code></p>
                <p>Documentație Swagger:</p>
                <p><code>/docs</code></p>
            </div>
        </body>
    </html>
    """


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "Lazarus Safe API"
    }


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest):
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
