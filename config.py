import os
from pathlib import Path


class Settings:
    # === BASE ===
    BASE_DIR = Path(__file__).resolve().parent.parent

    # === DATABASE ===
    DB_NAME = os.getenv("DB_NAME", "lazarus_safe_v2.db")
    DB_PATH = BASE_DIR / DB_NAME

    # === SERVER ===
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", 8000))

    # === API ===
    API_TITLE = "Lazarus Safe API v2"
    API_VERSION = "1.0.0"

    # === GEO ===
    GEO_PROVIDER = os.getenv("GEO_PROVIDER", "mock")  # mock / nominatim
    GEO_TIMEOUT = int(os.getenv("GEO_TIMEOUT", 5))

    # === INCIDENTS ===
    INCIDENT_DAYS_WINDOW = int(os.getenv("INCIDENT_DAYS_WINDOW", 60))

    # === RISK ===
    RISK_LOW = 5
    RISK_MEDIUM = 10
    RISK_HIGH = 16

    # === SECURITY ===
    ALLOW_ORIGINS = ["*"]

    # === DEBUG ===
    DEBUG = os.getenv("DEBUG", "true").lower() == "true"


# singleton
settings = Settings()