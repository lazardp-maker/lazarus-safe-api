import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "lazarus_safe.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    base_url TEXT NOT NULL,
    county TEXT,
    city TEXT,
    trust_level INTEGER NOT NULL DEFAULT 3,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_uid TEXT NOT NULL UNIQUE,
    incident_type TEXT NOT NULL,
    severity_level TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    event_date TEXT,
    published_date TEXT,
    days_ago INTEGER,
    address_text TEXT,
    location_text TEXT,
    city TEXT,
    county TEXT,
    latitude REAL,
    longitude REAL,
    geo_confidence REAL,
    ai_confidence REAL NOT NULL,
    is_verified INTEGER NOT NULL DEFAULT 0,
    verification_status TEXT NOT NULL,
    source_priority INTEGER NOT NULL DEFAULT 3,
    duplicate_group_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS incident_mentions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id INTEGER NOT NULL,
    source_id INTEGER NOT NULL,
    article_title TEXT NOT NULL,
    article_url TEXT NOT NULL,
    article_date TEXT,
    raw_text TEXT,
    extracted_location_text TEXT,
    extracted_type TEXT,
    ai_relevance_score REAL NOT NULL,
    is_duplicate INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS area_risk_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    county TEXT NOT NULL,
    city TEXT,
    locality_type TEXT NOT NULL DEFAULT 'county',
    crime_coefficient REAL NOT NULL DEFAULT 1.0,
    violence_coefficient REAL NOT NULL DEFAULT 1.0,
    theft_coefficient REAL NOT NULL DEFAULT 1.0,
    traffic_coefficient REAL NOT NULL DEFAULT 1.0,
    emergency_coefficient REAL NOT NULL DEFAULT 1.0,
    source_note TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analysis_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user_latitude REAL NOT NULL,
    user_longitude REAL NOT NULL,
    resolved_city TEXT,
    resolved_county TEXT,
    result_level TEXT NOT NULL,
    result_message TEXT NOT NULL,
    incidents_found INTEGER NOT NULL DEFAULT 0,
    sources_used INTEGER NOT NULL DEFAULT 0,
    created_by TEXT DEFAULT 'system'
);

CREATE INDEX IF NOT EXISTS idx_incidents_city_county
ON incidents(city, county);

CREATE INDEX IF NOT EXISTS idx_incidents_event_date
ON incidents(event_date);

CREATE INDEX IF NOT EXISTS idx_incidents_published_date
ON incidents(published_date);

CREATE INDEX IF NOT EXISTS idx_incidents_type
ON incidents(incident_type);

CREATE INDEX IF NOT EXISTS idx_incidents_verified
ON incidents(is_verified);

CREATE INDEX IF NOT EXISTS idx_mentions_incident_id
ON incident_mentions(incident_id);

CREATE INDEX IF NOT EXISTS idx_mentions_source_id
ON incident_mentions(source_id);

CREATE INDEX IF NOT EXISTS idx_area_risk_profiles_county_city
ON area_risk_profiles(county, city);

CREATE INDEX IF NOT EXISTS idx_sources_county_city_active
ON sources(county, city, is_active);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row

    # Optimizări și siguranță
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    conn.execute("PRAGMA cache_size = -20000;")  # aprox. 20MB cache
    return conn


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as conn:
        conn.executescript(SCHEMA_SQL)
    print(f"Database initialized successfully: {DB_PATH.name}")


def db_exists() -> bool:
    return DB_PATH.exists()


def ensure_db_initialized() -> None:
    if not db_exists():
        init_db()
        return

    # Dacă fișierul există, dar vrei să te asiguri că schema e completă
    with get_db() as conn:
        conn.executescript(SCHEMA_SQL)


if __name__ == "__main__":
    init_db()
