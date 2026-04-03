import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "lazarus_safe_v2.db"

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('official', 'press', 'other')),
    base_url TEXT NOT NULL,
    county TEXT,
    city TEXT,
    trust_level INTEGER NOT NULL DEFAULT 3 CHECK (trust_level BETWEEN 1 AND 5),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, base_url)
);

CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    content TEXT,
    published_at TEXT,
    county TEXT,
    city TEXT,
    detected_incident_type TEXT,
    detected_severity TEXT,
    ai_confidence REAL,
    is_processed INTEGER NOT NULL DEFAULT 0 CHECK (is_processed IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_uid TEXT NOT NULL UNIQUE,
    incident_type TEXT NOT NULL CHECK (
        incident_type IN (
            'homicide',
            'sexual_violence',
            'robbery',
            'theft',
            'violence',
            'traffic',
            'emergency',
            'public_order',
            'general'
        )
    ),
    severity_level TEXT NOT NULL CHECK (
        severity_level IN ('low', 'medium', 'high', 'critical')
    ),
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
    ai_confidence REAL NOT NULL DEFAULT 0.0,
    is_verified INTEGER NOT NULL DEFAULT 0 CHECK (is_verified IN (0, 1)),
    verification_status TEXT NOT NULL DEFAULT 'unverified' CHECK (
        verification_status IN ('unverified', 'ai_checked', 'verified', 'rejected')
    ),
    source_priority INTEGER NOT NULL DEFAULT 3 CHECK (source_priority BETWEEN 1 AND 5),
    duplicate_group_id TEXT,
    primary_source_id INTEGER,
    article_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (primary_source_id) REFERENCES sources(id) ON DELETE SET NULL,
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS incident_mentions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id INTEGER NOT NULL,
    source_id INTEGER NOT NULL,
    article_id INTEGER,
    mention_title TEXT,
    mention_url TEXT,
    published_date TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE CASCADE,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE,
    FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE SET NULL,
    UNIQUE(incident_id, source_id, mention_url)
);

CREATE TABLE IF NOT EXISTS area_risk_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    county TEXT NOT NULL,
    city TEXT,
    locality_type TEXT NOT NULL DEFAULT 'county' CHECK (
        locality_type IN ('county', 'city', 'sector', 'commune', 'village')
    ),
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
    request_lat REAL,
    request_lng REAL,
    resolved_county TEXT,
    resolved_city TEXT,
    level TEXT,
    message TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_area_risk_profiles_county_city_type
ON area_risk_profiles (
    county,
    COALESCE(city, '__NULL__'),
    locality_type
);

CREATE INDEX IF NOT EXISTS idx_sources_county_city
ON sources(county, city);

CREATE INDEX IF NOT EXISTS idx_sources_active
ON sources(is_active);

CREATE INDEX IF NOT EXISTS idx_articles_source_id
ON articles(source_id);

CREATE INDEX IF NOT EXISTS idx_articles_published_at
ON articles(published_at);

CREATE INDEX IF NOT EXISTS idx_articles_county_city
ON articles(county, city);

CREATE INDEX IF NOT EXISTS idx_articles_detected_type
ON articles(detected_incident_type);

CREATE INDEX IF NOT EXISTS idx_incidents_type
ON incidents(incident_type);

CREATE INDEX IF NOT EXISTS idx_incidents_county_city
ON incidents(county, city);

CREATE INDEX IF NOT EXISTS idx_incidents_published_date
ON incidents(published_date);

CREATE INDEX IF NOT EXISTS idx_incidents_event_date
ON incidents(event_date);

CREATE INDEX IF NOT EXISTS idx_incidents_verification_status
ON incidents(verification_status);

CREATE INDEX IF NOT EXISTS idx_incidents_duplicate_group_id
ON incidents(duplicate_group_id);

CREATE INDEX IF NOT EXISTS idx_incident_mentions_incident_id
ON incident_mentions(incident_id);

CREATE INDEX IF NOT EXISTS idx_incident_mentions_source_id
ON incident_mentions(source_id);

CREATE INDEX IF NOT EXISTS idx_area_risk_profiles_county_city
ON area_risk_profiles(county, city);

CREATE INDEX IF NOT EXISTS idx_analysis_runs_created_at
ON analysis_runs(created_at);
"""

TRIGGERS_SQL = """
CREATE TRIGGER IF NOT EXISTS trg_sources_updated_at
AFTER UPDATE ON sources
FOR EACH ROW
BEGIN
    UPDATE sources
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_articles_updated_at
AFTER UPDATE ON articles
FOR EACH ROW
BEGIN
    UPDATE articles
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_incidents_updated_at
AFTER UPDATE ON incidents
FOR EACH ROW
BEGIN
    UPDATE incidents
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_area_risk_profiles_updated_at
AFTER UPDATE ON area_risk_profiles
FOR EACH ROW
BEGIN
    UPDATE area_risk_profiles
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = OLD.id;
END;
"""

def initialize_database() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    try:
        conn.executescript(SCHEMA_SQL)
        conn.executescript(TRIGGERS_SQL)
        conn.commit()
    finally:
        conn.close()

def print_summary() -> None:
    conn = sqlite3.connect(DB_PATH)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]
        print(f"Database initialized successfully: {DB_PATH}")
        print("Tables:")
        for table in tables:
            print(f" - {table}")
    finally:
        conn.close()

def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    initialize_database()
    print_summary()

if __name__ == "__main__":
    main()