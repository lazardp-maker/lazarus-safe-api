from __future__ import annotations

import os
import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = Path(os.getenv("DB_PATH", str(DATA_DIR / "lazarus_safe.db"))).resolve()


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
    ai_confidence REAL CHECK (ai_confidence IS NULL OR (ai_confidence >= 0 AND ai_confidence <= 1)),
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
    geo_confidence REAL CHECK (geo_confidence IS NULL OR (geo_confidence >= 0 AND geo_confidence <= 1)),
    ai_confidence REAL NOT NULL DEFAULT 0.0 CHECK (ai_confidence >= 0 AND ai_confidence <= 1),
    is_verified INTEGER NOT NULL DEFAULT 0 CHECK (is_verified IN (0, 1)),
    verification_status TEXT NOT NULL DEFAULT 'unverified' CHECK (
        verification_status IN ('unverified', 'ai_checked', 'verified', 'rejected', 'detected_by_rules', 'auto_parsed')
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
    city TEXT NOT NULL DEFAULT '',
    locality_type TEXT NOT NULL DEFAULT 'county' CHECK (
        locality_type IN ('county', 'city', 'sector', 'commune', 'village')
    ),
    crime_coefficient REAL NOT NULL DEFAULT 1.0 CHECK (crime_coefficient >= 0),
    violence_coefficient REAL NOT NULL DEFAULT 1.0 CHECK (violence_coefficient >= 0),
    theft_coefficient REAL NOT NULL DEFAULT 1.0 CHECK (theft_coefficient >= 0),
    traffic_coefficient REAL NOT NULL DEFAULT 1.0 CHECK (traffic_coefficient >= 0),
    emergency_coefficient REAL NOT NULL DEFAULT 1.0 CHECK (emergency_coefficient >= 0),
    source_note TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(county, city, locality_type)
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

CREATE INDEX IF NOT EXISTS idx_sources_county_city ON sources(county, city);
CREATE INDEX IF NOT EXISTS idx_sources_active ON sources(is_active);
CREATE INDEX IF NOT EXISTS idx_articles_source_id ON articles(source_id);
CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at);
CREATE INDEX IF NOT EXISTS idx_articles_county_city ON articles(county, city);
CREATE INDEX IF NOT EXISTS idx_articles_detected_type ON articles(detected_incident_type);
CREATE INDEX IF NOT EXISTS idx_articles_is_processed ON articles(is_processed);
CREATE INDEX IF NOT EXISTS idx_incidents_type ON incidents(incident_type);
CREATE INDEX IF NOT EXISTS idx_incidents_county_city ON incidents(county, city);
CREATE INDEX IF NOT EXISTS idx_incidents_county_city_type ON incidents(county, city, incident_type);
CREATE INDEX IF NOT EXISTS idx_incidents_published_date ON incidents(published_date);
CREATE INDEX IF NOT EXISTS idx_incidents_event_date ON incidents(event_date);
CREATE INDEX IF NOT EXISTS idx_incidents_verification_status ON incidents(verification_status);
CREATE INDEX IF NOT EXISTS idx_incidents_duplicate_group_id ON incidents(duplicate_group_id);
CREATE INDEX IF NOT EXISTS idx_incidents_primary_source_id ON incidents(primary_source_id);
CREATE INDEX IF NOT EXISTS idx_incidents_article_id ON incidents(article_id);
CREATE INDEX IF NOT EXISTS idx_incident_mentions_incident_id ON incident_mentions(incident_id);
CREATE INDEX IF NOT EXISTS idx_incident_mentions_source_id ON incident_mentions(source_id);
CREATE INDEX IF NOT EXISTS idx_incident_mentions_article_id ON incident_mentions(article_id);
CREATE INDEX IF NOT EXISTS idx_area_risk_profiles_county_city ON area_risk_profiles(county, city);
CREATE INDEX IF NOT EXISTS idx_analysis_runs_created_at ON analysis_runs(created_at);
"""


TRIGGERS_SQL = """
CREATE TRIGGER IF NOT EXISTS trg_sources_updated_at
AFTER UPDATE ON sources
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE sources
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_articles_updated_at
AFTER UPDATE ON articles
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE articles
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_incidents_updated_at
AFTER UPDATE ON incidents
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE incidents
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = OLD.id;
END;

CREATE TRIGGER IF NOT EXISTS trg_area_risk_profiles_updated_at
AFTER UPDATE ON area_risk_profiles
FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE area_risk_profiles
    SET updated_at = CURRENT_TIMESTAMP
    WHERE id = OLD.id;
END;
"""


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn


def get_db_path() -> str:
    return str(DB_PATH)


def list_tables(conn: sqlite3.Connection | None = None) -> list[str]:
    owns_connection = conn is None
    if owns_connection:
        conn = get_connection()

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
        """)
        return [row["name"] for row in cursor.fetchall()]
    finally:
        if owns_connection and conn is not None:
            conn.close()


def list_columns(table_name: str, conn: sqlite3.Connection | None = None) -> list[str]:
    owns_connection = conn is None
    if owns_connection:
        conn = get_connection()

    try:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        rows = cursor.fetchall()
        return [row["name"] for row in rows]
    finally:
        if owns_connection and conn is not None:
            conn.close()


def validate_critical_tables(conn: sqlite3.Connection | None = None) -> None:
    required_tables = {
        "sources",
        "articles",
        "incidents",
        "incident_mentions",
        "area_risk_profiles",
        "analysis_runs",
    }

    existing_tables = set(list_tables(conn))
    missing_tables = sorted(required_tables - existing_tables)

    if missing_tables:
        raise RuntimeError(f"Lipsesc tabele critice după init: {missing_tables}")


def validate_critical_columns(conn: sqlite3.Connection | None = None) -> None:
    owns_connection = conn is None
    if owns_connection:
        conn = get_connection()

    try:
        expected = {
            "incidents": {"incident_uid", "incident_type", "severity_level", "days_ago", "county", "city"},
            "area_risk_profiles": {"county", "city", "locality_type", "crime_coefficient"},
        }

        for table_name, expected_columns in expected.items():
            existing_columns = set(list_columns(table_name, conn))
            missing_columns = sorted(expected_columns - existing_columns)
            if missing_columns:
                raise RuntimeError(
                    f"Lipsesc coloane critice în tabela {table_name}: {missing_columns}"
                )
    finally:
        if owns_connection and conn is not None:
            conn.close()


def initialize_database() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    conn = get_connection()
    try:
        print("[db] Creating tables...")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA temp_store = MEMORY;")

        conn.executescript(SCHEMA_SQL)
        conn.executescript(TRIGGERS_SQL)
        conn.commit()

        validate_critical_tables(conn)
        validate_critical_columns(conn)

        print(f"[db] Database initialized: {DB_PATH}")
        print(f"[db] Tables: {list_tables(conn)}")
        print(f"[db] area_risk_profiles columns: {list_columns('area_risk_profiles', conn)}")
    finally:
        conn.close()


def print_summary() -> None:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode;")
        row = cursor.fetchone()
        journal_mode = row[0] if row else "unknown"

        print(f"[db] Database initialized successfully: {DB_PATH}")
        print(f"[db] Journal mode: {journal_mode}")
        print("[db] Tables:")
        for table in list_tables(conn):
            print(f" - {table}")
    finally:
        conn.close()


def main() -> None:
    initialize_database()
    print_summary()


if __name__ == "__main__":
    main()