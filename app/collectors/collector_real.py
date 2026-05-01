from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.collectors.parsers import build_parser_result, normalize_text
from app.db import get_connection, get_db_path

REQUEST_TIMEOUT = 15
GEOCODE_TIMEOUT = 12
GEOCODE_SLEEP_SECONDS = 1.1

MAX_LINKS_PER_SOURCE = 80
MAX_ARTICLES_TO_PROCESS = 25
MIN_TITLE_LEN = 18
MIN_CONTENT_LEN = 120
MIN_AI_CONFIDENCE = 0.70

MATCH_LOOKBACK_DAYS = 14
MATCH_SCORE_THRESHOLD = 0.62
MAX_TITLE_TOKENS = 12

REQUIRE_LOCATION_FOR_PRESS = True
REQUIRE_DATE_FOR_PRESS = True

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 LazarusSafeCollector/3.5",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ro,en;q=0.8",
    "Connection": "keep-alive",
}

GEOCODE_HEADERS = {
    "User-Agent": "LazarusSafe/1.0 (risk-intelligence-app; contact: lazardp@gmail.com)",
    "Accept-Language": "ro,en;q=0.8",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

_geocode_cache: dict[str, Optional[tuple[float, float, float, str]]] = {}


@dataclass
class SourceItem:
    id: int
    name: str
    source_type: str
    base_url: str
    county: Optional[str]
    city: Optional[str]
    trust_level: int


@dataclass
class SourceRunStats:
    candidates_found: int = 0
    candidates_checked: int = 0
    article_pages_loaded: int = 0
    articles_skipped_existing: int = 0
    articles_skipped_short: int = 0
    articles_skipped_noise: int = 0
    articles_skipped_parser: int = 0
    articles_skipped_no_location: int = 0
    articles_skipped_no_date: int = 0
    articles_saved: int = 0
    incidents_saved: int = 0
    incidents_linked_existing: int = 0
    geocode_attempts: int = 0
    geocode_success: int = 0
    geocode_failed: int = 0
    errors: int = 0


STOP_TOKENS = {
    "in", "din", "la", "pe", "cu", "de", "si", "și", "un", "o", "a", "au",
    "dintr", "dintr-o", "dintrun", "dintre", "sau", "pentru", "care", "catre",
    "către", "asupra", "caz", "cazul", "privind", "dupa", "după", "ultimele",
    "zile", "luni", "azi", "ieri", "maine", "mâine", "politistii", "polițiștii",
    "politia", "poliția", "arges", "argeș", "bucuresti", "bucurești",
}

NOISE_KEYWORDS = [
    "cookie", "cookies", "politica de confidentialitate", "politica de confidențialitate",
    "termeni si conditii", "termeni și condiții", "acceptati modifica setarile",
    "acceptați modificați setările", "continuarea navigarii", "continuarea navigării",
    "publicitate", "abonare newsletter", "newsletter", "opinia specialistilor",
    "opinia specialiștilor", "advertorial", "sponsorizat", "digitalizarea",
    "salariul minim", "programul cu publicul", "program cu publicul", "ghiseelor",
    "ghișeelor", "documente necesare", "eliberarii de acte", "eliberării de acte",
    "protectia datelor", "protecția datelor", "regulament de organizare",
    "plati efectuate", "plăți efectuate", "admitere in", "admitere în",
    "anunt", "anunț", "click aici", "mai multe detalii", "campanie de informare",
    "sistem de informatii schengen", "selectie personal", "selecție personal",
    "registrul unic", "programul interreg", "programul transport", "proiectului",
    "imbunatatirea rezilientei", "îmbunătățirea rezilienței", "cumpara in siguranta",
    "cumpără în siguranță", "prioritatea politistilor", "prioritatea polițiștilor",
    "plan de management", "actiune integrata", "acțiune integrată",
    "transparentei intereselor", "transparenta intereselor",
]

PUBLIC_SAFETY_CONTEXT = [
    "politistii", "polițiștii", "politia", "poliția", "ipj", "isu", "igsu", "dsu",
    "mai", "jandarmi", "jandarmeria", "parchet", "procuror", "dosar penal",
    "retinut", "reținut", "arest", "arestare", "perchezitie", "percheziție",
    "apel 112", "smurd", "interventie", "intervenție", "victima", "victime",
    "suspect", "agresor", "infractiune", "infracțiune",
]

SERIOUS_TYPES = {"homicide", "sexual_violence", "robbery"}


def clean_text(text: str) -> str:
    return " ".join((text or "").split()).strip()


def normalize_for_match(value: Optional[str]) -> str:
    return normalize_text(value) or ""


def safe_float(value, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def haversine_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    import math

    radius = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def is_official_source_name(name: Optional[str]) -> bool:
    value = normalize_for_match(name)
    return any(token in value for token in ("politia", "ipj", "mai", "isu", "igsu", "dsu", "parchet", "diicot", "jandarmeria"))


def is_public_safety_article(text: str, source: SourceItem) -> bool:
    if source.source_type == "official" or is_official_source_name(source.name):
        return True

    t = normalize_for_match(text)
    return any(token in t for token in PUBLIC_SAFETY_CONTEXT)


def is_noise(text: str) -> bool:
    t = normalize_for_match(text)
    return any(keyword in t for keyword in NOISE_KEYWORDS)


def has_minimum_geo(parsed: dict, source: SourceItem) -> bool:
    return bool(
        parsed.get("county")
        or parsed.get("city")
        or source.county
        or source.city
        or parsed.get("location_text")
        or parsed.get("geo_query")
    )


def should_keep_parsed_result(parsed: dict, source: SourceItem, combined_text: str) -> tuple[bool, str]:
    if not parsed.get("title"):
        return False, "missing_title"

    if parsed.get("incident_type") == "general":
        return False, "general_type"

    if float(parsed.get("ai_confidence", 0.0)) < MIN_AI_CONFIDENCE:
        return False, "low_confidence"

    if is_noise(combined_text):
        return False, "noise"

    if not is_public_safety_article(combined_text, source):
        return False, "no_public_safety_context"

    is_official = source.source_type == "official" or is_official_source_name(source.name)
    is_serious = parsed.get("incident_type") in SERIOUS_TYPES

    if REQUIRE_LOCATION_FOR_PRESS and not is_official and not has_minimum_geo(parsed, source):
        return False, "missing_location"

    if REQUIRE_DATE_FOR_PRESS and not is_official and not parsed.get("published_date"):
        if not is_serious:
            return False, "missing_date"

    return True, "ok"


def get_active_sources() -> list[SourceItem]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, name, source_type, base_url, county, city, trust_level
            FROM sources
            WHERE is_active = 1
            ORDER BY trust_level DESC, id ASC
            """
        )
        rows = cursor.fetchall()
        return [
            SourceItem(
                id=row["id"],
                name=row["name"],
                source_type=row["source_type"],
                base_url=row["base_url"],
                county=normalize_text(row["county"]) or None,
                city=normalize_text(row["city"]) or None,
                trust_level=row["trust_level"],
            )
            for row in rows
        ]
    finally:
        conn.close()


def fetch_page(session: requests.Session, url: str) -> Optional[str]:
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT, headers=DEFAULT_HEADERS, allow_redirects=True)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            logger.warning("Continut non-HTML ignorat: %s | %s", url, content_type)
            return None
        response.encoding = response.apparent_encoding or response.encoding
        return response.text
    except requests.RequestException as exc:
        logger.warning("Nu s-a putut accesa %s | %s", url, exc)
        return None


def same_domain(base_url: str, candidate_url: str) -> bool:
    base_netloc = urlparse(base_url).netloc.lower().replace("www.", "")
    cand_netloc = urlparse(candidate_url).netloc.lower().replace("www.", "")
    return base_netloc == cand_netloc


def is_valid_article_url(url: str) -> bool:
    if not url:
        return False

    lowered = url.lower()
    blocked_suffixes = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip")
    blocked_fragments = [
        "javascript:", "mailto:", "/tag/", "/eticheta/", "/categorie/", "/category/",
        "/author/", "/autor/", "/page/", "/privacy", "/cookie", "/termeni",
    ]

    if lowered.startswith("javascript:") or lowered.startswith("mailto:"):
        return False
    if any(fragment in lowered for fragment in blocked_fragments):
        return False
    if lowered.endswith(blocked_suffixes):
        return False
    return True


def extract_candidate_links(html: str, base_url: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[tuple[str, str]] = []
    seen_urls: set[str] = set()

    for tag in soup.find_all("a", href=True):
        href = clean_text(tag.get("href", ""))
        text = clean_text(tag.get_text(" ", strip=True))

        if len(text) < MIN_TITLE_LEN:
            continue
        if is_noise(text):
            continue
        if not is_valid_article_url(href):
            continue

        full_url = urljoin(base_url, href)
        if not full_url.startswith("http"):
            continue
        if not same_domain(base_url, full_url):
            continue

        normalized_url = full_url.strip()
        if normalized_url in seen_urls:
            continue

        seen_urls.add(normalized_url)
        results.append((text, normalized_url))

    return results[:MAX_LINKS_PER_SOURCE]


def extract_article_content(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")

    title = ""
    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content"):
        title = clean_text(og_title["content"])
    elif soup.title and soup.title.text:
        title = clean_text(soup.title.text)

    paragraphs: list[str] = []
    for p in soup.find_all("p"):
        text = clean_text(p.get_text(" ", strip=True))
        if len(text) >= 35 and not is_noise(text):
            paragraphs.append(text)

    content = " ".join(paragraphs[:40]).strip()
    return title, content


def article_exists(conn, url: str) -> bool:
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM articles WHERE url = ? LIMIT 1", (url,))
    return cursor.fetchone() is not None


def normalize_query_string(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = clean_text(value).strip(" ,")
    return value or None


def infer_geo_confidence_from_query(query: str) -> float:
    q = normalize_text(query or "")

    if "strada" in q or "str." in q or "bulevardul" in q or "bd." in q or "calea" in q:
        return 0.88
    if "piata" in q or "piața" in q or "intersectia" in q or "intersecția" in q:
        return 0.84
    if "cartier" in q or "zona" in q:
        return 0.78
    if "sector" in q:
        return 0.72

    parts = [p.strip() for p in q.split(",") if p.strip()]
    if len(parts) >= 3:
        return 0.70
    if len(parts) == 2:
        return 0.58
    return 0.45


def geocode_query(session: requests.Session, query: Optional[str]) -> Optional[tuple[float, float, float, str]]:
    query = normalize_query_string(query)
    if not query:
        return None

    cache_key = query.lower()
    if cache_key in _geocode_cache:
        return _geocode_cache[cache_key]

    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "ro", "addressdetails": 1}

    try:
        response = session.get(url, params=params, headers=GEOCODE_HEADERS, timeout=GEOCODE_TIMEOUT)
        response.raise_for_status()
        data = response.json()

        if not data:
            _geocode_cache[cache_key] = None
            time.sleep(GEOCODE_SLEEP_SECONDS)
            return None

        item = data[0]
        lat = float(item["lat"])
        lng = float(item["lon"])
        geo_confidence = infer_geo_confidence_from_query(query)
        display_name = clean_text(item.get("display_name", "")) or query

        result = (lat, lng, geo_confidence, display_name)
        _geocode_cache[cache_key] = result
        time.sleep(GEOCODE_SLEEP_SECONDS)
        return result

    except Exception as exc:
        logger.warning("Geocoding esuat pentru '%s' | %s", query, exc)
        _geocode_cache[cache_key] = None
        return None


def build_geocode_candidates(parsed: dict, source: SourceItem) -> list[str]:
    candidates: list[str] = []

    geo_query = normalize_query_string(parsed.get("geo_query"))
    location_text = normalize_query_string(parsed.get("location_text"))
    city = normalize_query_string(parsed.get("city") or source.city)
    county = normalize_query_string(parsed.get("county") or source.county)

    if geo_query:
        candidates.append(geo_query)
    if location_text and city and county:
        candidates.append(f"{location_text}, {city}, {county}, Romania")
    if location_text and city:
        candidates.append(f"{location_text}, {city}, Romania")
    if city and county:
        candidates.append(f"{city}, {county}, Romania")
    if city:
        candidates.append(f"{city}, Romania")
    if county:
        candidates.append(f"{county}, Romania")

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        c = normalize_query_string(candidate)
        if not c:
            continue
        key = c.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)

    return deduped


def geocode_parsed_incident(session: requests.Session, parsed: dict, source: SourceItem):
    for candidate in build_geocode_candidates(parsed, source):
        result = geocode_query(session, candidate)
        if result:
            lat, lng, geo_confidence, display_name = result
            return lat, lng, geo_confidence, candidate, display_name
    return None, None, None, None, None


def upsert_article(conn, source: SourceItem, parsed: dict) -> int:
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO articles (
            source_id, title, url, content, published_at, county, city,
            detected_incident_type, detected_severity, ai_confidence, is_processed
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ON CONFLICT(url) DO UPDATE SET
            title = excluded.title,
            content = excluded.content,
            published_at = COALESCE(excluded.published_at, articles.published_at),
            county = COALESCE(excluded.county, articles.county),
            city = COALESCE(excluded.city, articles.city),
            detected_incident_type = COALESCE(excluded.detected_incident_type, articles.detected_incident_type),
            detected_severity = COALESCE(excluded.detected_severity, articles.detected_severity),
            ai_confidence = excluded.ai_confidence,
            is_processed = 1
        """,
        (
            source.id,
            parsed["title"],
            parsed["url"],
            parsed["summary"],
            parsed["published_date"],
            parsed["county"] or source.county,
            parsed["city"] or source.city,
            parsed["incident_type"],
            parsed["severity_level"],
            parsed["ai_confidence"],
        ),
    )

    cursor.execute("SELECT id FROM articles WHERE url = ?", (parsed["url"],))
    row = cursor.fetchone()
    if not row:
        raise RuntimeError(f"Nu s-a putut salva articolul: {parsed['url']}")
    return row["id"]


def get_incident_id_by_uid(conn, incident_uid: str) -> Optional[int]:
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM incidents WHERE incident_uid = ? LIMIT 1", (incident_uid,))
    row = cursor.fetchone()
    return row["id"] if row else None


def tokenize_title(value: Optional[str]) -> set[str]:
    text = normalize_for_match(value)
    tokens = re.findall(r"[a-z0-9]{3,}", text)
    cleaned = [t for t in tokens if t not in STOP_TOKENS]
    return set(cleaned[:MAX_TITLE_TOKENS])


def jaccard_similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    union = len(a | b)
    return 0.0 if union == 0 else len(a & b) / union


def get_recent_candidate_incidents_for_match(conn, parsed: dict, source: SourceItem) -> list[dict]:
    incident_type = parsed.get("incident_type")
    county = parsed.get("county") or source.county
    city = parsed.get("city") or source.city
    published_date = parsed.get("published_date")

    if not incident_type or not county:
        return []

    where_parts = [
        "incident_type = ?",
        "county = ?",
        "date(COALESCE(event_date, published_date, created_at)) >= date('now', ?)",
    ]
    params: list[object] = [incident_type, county, f"-{MATCH_LOOKBACK_DAYS} days"]

    if city:
        where_parts.append("(city = ? OR city IS NULL OR city = '')")
        params.append(city)

    if published_date:
        where_parts.append("ABS(julianday(COALESCE(event_date, published_date, created_at)) - julianday(?)) <= 3")
        params.append(published_date)

    query = f"""
        SELECT *
        FROM incidents
        WHERE {" AND ".join(where_parts)}
        ORDER BY COALESCE(date(event_date), date(published_date), date(created_at)) DESC, id DESC
        LIMIT 25
    """

    cursor = conn.cursor()
    cursor.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def compute_incident_match_score(existing: dict, parsed: dict, source: SourceItem) -> float:
    score = 0.0

    if normalize_for_match(existing.get("incident_type")) != normalize_for_match(parsed.get("incident_type")):
        return 0.0
    score += 0.22

    existing_county = normalize_for_match(existing.get("county"))
    parsed_county = normalize_for_match(parsed.get("county") or source.county)
    if existing_county and parsed_county and existing_county == parsed_county:
        score += 0.14
    elif existing_county or parsed_county:
        return 0.0

    existing_city = normalize_for_match(existing.get("city"))
    parsed_city = normalize_for_match(parsed.get("city") or source.city)
    if existing_city and parsed_city and existing_city == parsed_city:
        score += 0.10
    elif not existing_city or not parsed_city:
        score += 0.03

    existing_date = normalize_for_match(existing.get("published_date") or existing.get("event_date"))
    parsed_date = normalize_for_match(parsed.get("published_date"))
    if existing_date and parsed_date:
        score += 0.16 if existing_date == parsed_date else 0.04

    title_sim = jaccard_similarity(tokenize_title(existing.get("title")), tokenize_title(parsed.get("title")))
    score += min(title_sim * 0.22, 0.22)

    existing_lat = safe_float(existing.get("latitude"))
    existing_lng = safe_float(existing.get("longitude"))
    parsed_lat = safe_float(parsed.get("latitude"))
    parsed_lng = safe_float(parsed.get("longitude"))

    if None not in (existing_lat, existing_lng, parsed_lat, parsed_lng):
        dist = haversine_meters(existing_lat, existing_lng, parsed_lat, parsed_lng)
        if dist <= 120:
            score += 0.24
        elif dist <= 350:
            score += 0.18
        elif dist <= 800:
            score += 0.10

    if int(existing.get("is_verified") or 0) == 1 or source.source_type == "official":
        score += 0.03

    return min(score, 1.0)


def find_matching_incident(conn, parsed: dict, source: SourceItem) -> Optional[int]:
    candidates = get_recent_candidate_incidents_for_match(conn, parsed, source)
    best_id: Optional[int] = None
    best_score = 0.0

    for candidate in candidates:
        score = compute_incident_match_score(candidate, parsed, source)
        if score > best_score:
            best_score = score
            best_id = candidate["id"]

    if best_id is not None and best_score >= MATCH_SCORE_THRESHOLD:
        logger.info("MATCH incident existent | incident_id=%s | score=%.3f", best_id, best_score)
        return best_id

    return None


def save_incident_mention(conn, incident_id: int, source: SourceItem, article_id: int, mention_title: str, mention_url: str, published_date: Optional[str]) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR IGNORE INTO incident_mentions (
            incident_id, source_id, article_id, mention_title, mention_url, published_date
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (incident_id, source.id, article_id, mention_title, mention_url, published_date),
    )


def update_existing_incident_geo_if_better(conn, incident_id: int, parsed: dict, source: SourceItem) -> None:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM incidents WHERE id = ? LIMIT 1", (incident_id,))
    row = cursor.fetchone()
    if not row:
        return

    existing_lat = row["latitude"]
    existing_lng = row["longitude"]
    existing_geo_conf = row["geo_confidence"]

    should_update_geo = False
    if parsed.get("latitude") is not None and parsed.get("longitude") is not None:
        if existing_lat is None or existing_lng is None:
            should_update_geo = True
        else:
            existing_conf = float(existing_geo_conf) if existing_geo_conf is not None else 0.0
            new_conf = float(parsed.get("geo_confidence") or 0.0)
            should_update_geo = new_conf > existing_conf

    new_is_official = bool(source.source_type == "official" or parsed.get("is_verified") == 1)
    new_priority = max(int(source.trust_level or 3), int(row["source_priority"] or 3))

    cursor.execute(
        """
        UPDATE incidents
        SET
            city = COALESCE(?, city),
            county = COALESCE(?, county),
            location_text = COALESCE(?, location_text),
            address_text = COALESCE(?, address_text),
            latitude = CASE WHEN ? THEN ? ELSE latitude END,
            longitude = CASE WHEN ? THEN ? ELSE longitude END,
            geo_confidence = CASE WHEN ? THEN ? ELSE geo_confidence END,
            ai_confidence = CASE WHEN ? > ai_confidence THEN ? ELSE ai_confidence END,
            is_verified = CASE WHEN ? = 1 THEN 1 ELSE is_verified END,
            verification_status = CASE
                WHEN ? = 1 THEN 'verified'
                WHEN verification_status = 'unverified' AND ? IS NOT NULL THEN ?
                ELSE verification_status
            END,
            source_priority = CASE WHEN ? > source_priority THEN ? ELSE source_priority END,
            primary_source_id = CASE
                WHEN ? = 1 THEN ?
                WHEN primary_source_id IS NULL THEN ?
                ELSE primary_source_id
            END
        WHERE id = ?
        """,
        (
            parsed.get("city") or source.city,
            parsed.get("county") or source.county,
            parsed.get("location_text"),
            parsed.get("address_text") or parsed.get("geo_display_name") or parsed.get("geo_query"),
            1 if should_update_geo else 0,
            parsed.get("latitude"),
            1 if should_update_geo else 0,
            parsed.get("longitude"),
            1 if should_update_geo else 0,
            parsed.get("geo_confidence"),
            float(parsed.get("ai_confidence") or 0.0),
            parsed.get("ai_confidence"),
            parsed.get("is_verified"),
            parsed.get("is_verified"),
            parsed.get("verification_status"),
            parsed.get("verification_status"),
            new_priority,
            new_priority,
            1 if new_is_official else 0,
            source.id,
            source.id,
            incident_id,
        ),
    )


def save_new_incident(conn, source: SourceItem, article_id: int, parsed: dict) -> int:
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO incidents (
            incident_uid, incident_type, severity_level, title, summary,
            event_date, published_date, days_ago, address_text, location_text,
            city, county, latitude, longitude, geo_confidence, ai_confidence,
            is_verified, verification_status, source_priority, duplicate_group_id,
            primary_source_id, article_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            parsed["incident_uid"],
            parsed["incident_type"],
            parsed["severity_level"],
            parsed["title"],
            parsed["summary"],
            None,
            parsed["published_date"],
            parsed["days_ago"],
            parsed.get("address_text") or parsed.get("geo_display_name") or parsed.get("geo_query"),
            parsed.get("location_text"),
            parsed["city"] or source.city,
            parsed["county"] or source.county,
            parsed.get("latitude"),
            parsed.get("longitude"),
            parsed.get("geo_confidence"),
            parsed["ai_confidence"],
            parsed["is_verified"],
            parsed["verification_status"],
            source.trust_level,
            None,
            source.id,
            article_id,
        ),
    )
    return cursor.lastrowid


def save_incident(conn, source: SourceItem, article_id: int, parsed: dict) -> tuple[int, bool]:
    incident_id = get_incident_id_by_uid(conn, parsed["incident_uid"])
    if not incident_id:
        incident_id = find_matching_incident(conn, parsed, source)

    if incident_id:
        update_existing_incident_geo_if_better(conn, incident_id, parsed, source)
        save_incident_mention(conn, incident_id, source, article_id, parsed["title"], parsed["url"], parsed["published_date"])
        return incident_id, False

    incident_id = save_new_incident(conn, source, article_id, parsed)
    save_incident_mention(conn, incident_id, source, article_id, parsed["title"], parsed["url"], parsed["published_date"])
    return incident_id, True


def enrich_parsed_with_source_fallback(parsed: dict, source: SourceItem) -> dict:
    if not parsed.get("county") and source.county:
        parsed["county"] = source.county
    if not parsed.get("city") and source.city:
        parsed["city"] = source.city

    if not parsed.get("geo_query"):
        parts = [parsed.get("location_text"), parsed.get("city"), parsed.get("county")]
        parts = [p for p in parts if p]
        if parts:
            parts.append("Romania")
            parsed["geo_query"] = ", ".join(parts)

    return parsed


def process_source(session: requests.Session, source: SourceItem) -> SourceRunStats:
    logger.info("=== Procesare sursa: %s ===", source.name)
    stats = SourceRunStats()

    html = fetch_page(session, source.base_url)
    if not html:
        stats.errors += 1
        return stats

    candidates = extract_candidate_links(html, source.base_url)
    stats.candidates_found = len(candidates)
    logger.info("Linkuri candidate extrase: %s", len(candidates))

    conn = get_connection()
    try:
        for link_text, article_url in candidates:
            if stats.candidates_checked >= MAX_ARTICLES_TO_PROCESS:
                break

            stats.candidates_checked += 1

            try:
                if article_exists(conn, article_url):
                    stats.articles_skipped_existing += 1
                    continue

                article_html = fetch_page(session, article_url)
                if not article_html:
                    continue

                stats.article_pages_loaded += 1

                page_title, article_content = extract_article_content(article_html)
                final_title = page_title if len(page_title) >= MIN_TITLE_LEN else link_text
                combined_text = f"{final_title} {article_content}".strip()

                if len(combined_text) < MIN_CONTENT_LEN:
                    stats.articles_skipped_short += 1
                    continue

                if is_noise(combined_text):
                    stats.articles_skipped_noise += 1
                    continue

                parsed = build_parser_result(
                    title=final_title,
                    content=article_content,
                    url=article_url,
                    source_name=source.name,
                )

                parsed = enrich_parsed_with_source_fallback(parsed, source)

                keep, reason = should_keep_parsed_result(parsed, source, combined_text)
                if not keep:
                    stats.articles_skipped_parser += 1
                    if reason == "missing_location":
                        stats.articles_skipped_no_location += 1
                    if reason == "missing_date":
                        stats.articles_skipped_no_date += 1
                    logger.info("IGNORAT | motiv=%s | sursa=%s | titlu=%s", reason, source.name, final_title)
                    continue

                stats.geocode_attempts += 1
                lat, lng, geo_confidence, geocode_used, geo_display_name = geocode_parsed_incident(session, parsed, source)

                parsed["latitude"] = lat
                parsed["longitude"] = lng
                parsed["geo_confidence"] = geo_confidence
                parsed["geo_display_name"] = geo_display_name

                if geocode_used and not parsed.get("geo_query"):
                    parsed["geo_query"] = geocode_used

                if lat is not None and lng is not None:
                    stats.geocode_success += 1
                else:
                    stats.geocode_failed += 1

                article_id = upsert_article(conn, source, parsed)
                stats.articles_saved += 1

                _, created_new_incident = save_incident(conn, source, article_id, parsed)
                if created_new_incident:
                    stats.incidents_saved += 1
                else:
                    stats.incidents_linked_existing += 1

                conn.commit()

                logger.info(
                    "SALVAT | sursa=%s | tip=%s | conf=%.3f | geo=%s | titlu=%s",
                    source.name,
                    parsed["incident_type"],
                    float(parsed["ai_confidence"]),
                    "DA" if parsed.get("latitude") is not None else "NU",
                    parsed["title"],
                )

            except Exception as exc:
                conn.rollback()
                stats.errors += 1
                logger.exception("Eroare la articol | sursa=%s | url=%s | eroare=%s", source.name, article_url, exc)

    finally:
        conn.close()

    logger.info(
        (
            "Sursa %s | candidate=%s | verificate=%s | pagini=%s | skip_existing=%s | "
            "skip_short=%s | skip_noise=%s | skip_parser=%s | skip_no_location=%s | "
            "skip_no_date=%s | articole_salvate=%s | incidente_noi=%s | legate=%s | "
            "geocode_success=%s | geocode_failed=%s | erori=%s"
        ),
        source.name,
        stats.candidates_found,
        stats.candidates_checked,
        stats.article_pages_loaded,
        stats.articles_skipped_existing,
        stats.articles_skipped_short,
        stats.articles_skipped_noise,
        stats.articles_skipped_parser,
        stats.articles_skipped_no_location,
        stats.articles_skipped_no_date,
        stats.articles_saved,
        stats.incidents_saved,
        stats.incidents_linked_existing,
        stats.geocode_success,
        stats.geocode_failed,
        stats.errors,
    )

    return stats


def main() -> None:
    logger.info("Pornire collector_real")
    logger.info("DB: %s", get_db_path())

    sources = get_active_sources()
    logger.info("Surse active incarcate: %s", len(sources))

    if not sources:
        logger.warning("Nu exista surse active in tabela sources.")
        return

    session = requests.Session()
    total = SourceRunStats()

    try:
        for source in sources:
            stats = process_source(session, source)
            for field in total.__dataclass_fields__:
                setattr(total, field, getattr(total, field) + getattr(stats, field))
    finally:
        session.close()

    logger.info(
        (
            "Colectare finalizata | candidate=%s | verificate=%s | articole_salvate=%s | "
            "incidente_noi=%s | incidente_legate=%s | skip_parser=%s | skip_no_location=%s | "
            "skip_no_date=%s | geocode_success=%s | geocode_failed=%s | erori=%s"
        ),
        total.candidates_found,
        total.candidates_checked,
        total.articles_saved,
        total.incidents_saved,
        total.incidents_linked_existing,
        total.articles_skipped_parser,
        total.articles_skipped_no_location,
        total.articles_skipped_no_date,
        total.geocode_success,
        total.geocode_failed,
        total.errors,
    )


if __name__ == "__main__":
    main()