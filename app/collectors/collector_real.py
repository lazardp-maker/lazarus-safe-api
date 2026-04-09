from __future__ import annotations

import logging
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
MIN_AI_CONFIDENCE = 0.62

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 LazarusSafeCollector/3.2",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ro,en;q=0.8",
    "Connection": "keep-alive",
}

GEOCODE_HEADERS = {
    "User-Agent": "LazarusSafe/1.0 (risk-intelligence-app)",
    "Accept-Language": "ro,en;q=0.8",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
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
    articles_saved: int = 0
    incidents_saved: int = 0
    incidents_linked_existing: int = 0
    geocode_attempts: int = 0
    geocode_success: int = 0
    geocode_failed: int = 0
    errors: int = 0


NOISE_KEYWORDS = [
    "programul cu publicul",
    "program cu publicul",
    "ghiseelor",
    "ghișeelor",
    "documente necesare",
    "eliberarii de acte",
    "eliberării de acte",
    "protectia datelor",
    "protecția datelor",
    "regulament de organizare",
    "plati efectuate",
    "plăți efectuate",
    "admitere in",
    "admitere în",
    "anunt",
    "anunț",
    "click aici",
    "mai multe detalii",
    "campanie de informare",
    "informatii de la politia rutiera",
    "informații de la poliția rutieră",
    "sistem de informatii schengen",
    "selectie personal",
    "selecție personal",
    "registrul unic",
    "programul interreg",
    "programul transport",
    "proiectului",
    "imbunatatirea rezilientei",
    "îmbunătățirea rezilienței",
    "cumpara in siguranta",
    "cumpără în siguranță",
    "prioritatea politistilor",
    "prioritatea polițiștilor",
    "plan de management",
    "actiune integrata",
    "acțiune integrată",
    "transparentei intereselor",
]


def clean_text(text: str) -> str:
    return " ".join(text.split()).strip()


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
        response = session.get(
            url,
            timeout=REQUEST_TIMEOUT,
            headers=DEFAULT_HEADERS,
            allow_redirects=True,
        )
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


def is_noise(text: str) -> bool:
    t = normalize_text(text) or ""
    return any(keyword in t for keyword in NOISE_KEYWORDS)


def same_domain(base_url: str, candidate_url: str) -> bool:
    base_netloc = urlparse(base_url).netloc.lower().replace("www.", "")
    cand_netloc = urlparse(candidate_url).netloc.lower().replace("www.", "")
    return base_netloc == cand_netloc


def is_valid_article_url(url: str) -> bool:
    if not url:
        return False

    lowered = url.lower()
    blocked_suffixes = (
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".zip",
    )
    blocked_fragments = [
        "javascript:",
        "mailto:",
        "/tag/",
        "/eticheta/",
        "/categorie/",
        "/category/",
        "/author/",
        "/autor/",
        "/page/",
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
        if len(text) >= 35:
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
    params = {
        "q": query,
        "format": "jsonv2",
        "limit": 1,
        "countrycodes": "ro",
        "addressdetails": 1,
    }

    try:
        response = session.get(
            url,
            params=params,
            headers=GEOCODE_HEADERS,
            timeout=GEOCODE_TIMEOUT,
        )
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
        candidates.append(f"{location_text}, {city}, {county}, romania")

    if location_text and city:
        candidates.append(f"{location_text}, {city}, romania")

    if city and county:
        candidates.append(f"{city}, {county}, romania")

    if city:
        candidates.append(f"{city}, romania")

    if county:
        candidates.append(f"{county}, romania")

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


def geocode_parsed_incident(
    session: requests.Session,
    parsed: dict,
    source: SourceItem,
) -> tuple[Optional[float], Optional[float], Optional[float], Optional[str], Optional[str]]:
    candidates = build_geocode_candidates(parsed, source)

    for candidate in candidates:
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
            source_id,
            title,
            url,
            content,
            published_at,
            county,
            city,
            location_text,
            detected_incident_type,
            detected_severity,
            ai_confidence,
            is_processed
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ON CONFLICT(url) DO UPDATE SET
            title = excluded.title,
            content = excluded.content,
            published_at = COALESCE(excluded.published_at, articles.published_at),
            county = COALESCE(excluded.county, articles.county),
            city = COALESCE(excluded.city, articles.city),
            location_text = COALESCE(excluded.location_text, articles.location_text),
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
            parsed.get("location_text"),
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


def update_existing_incident_geo_if_better(
    conn,
    incident_id: int,
    parsed: dict,
    source: SourceItem,
) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            city,
            county,
            location_text,
            latitude,
            longitude,
            geo_confidence,
            ai_confidence,
            verification_status,
            is_verified
        FROM incidents
        WHERE id = ?
        LIMIT 1
        """,
        (incident_id,),
    )
    row = cursor.fetchone()
    if not row:
        return

    existing_lat = row["latitude"]
    existing_lng = row["longitude"]
    existing_geo_conf = row["geo_confidence"]

    new_city = parsed.get("city") or row["city"] or source.city
    new_county = parsed.get("county") or row["county"] or source.county
    new_location_text = parsed.get("location_text") or row["location_text"]

    should_update_geo = False
    if parsed.get("latitude") is not None and parsed.get("longitude") is not None:
        if existing_lat is None or existing_lng is None:
            should_update_geo = True
        else:
            existing_conf = float(existing_geo_conf) if existing_geo_conf is not None else 0.0
            new_conf = float(parsed.get("geo_confidence") or 0.0)
            if new_conf > existing_conf:
                should_update_geo = True

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
            ai_confidence = CASE
                WHEN ai_confidence IS NULL THEN ?
                WHEN ? > ai_confidence THEN ?
                ELSE ai_confidence
            END,
            is_verified = CASE
                WHEN ? = 1 THEN 1
                ELSE is_verified
            END,
            verification_status = CASE
                WHEN ? = 1 THEN ?
                ELSE verification_status
            END
        WHERE id = ?
        """,
        (
            new_city,
            new_county,
            new_location_text,
            parsed.get("address_text"),
            1 if should_update_geo else 0,
            parsed.get("latitude"),
            1 if should_update_geo else 0,
            parsed.get("longitude"),
            1 if should_update_geo else 0,
            parsed.get("geo_confidence"),
            parsed.get("ai_confidence"),
            float(parsed.get("ai_confidence") or 0.0),
            parsed.get("ai_confidence"),
            parsed.get("is_verified"),
            parsed.get("is_verified"),
            parsed.get("verification_status"),
            incident_id,
        ),
    )


def save_incident_mention(
    conn,
    incident_id: int,
    source: SourceItem,
    article_id: int,
    mention_title: str,
    mention_url: str,
    published_date: Optional[str],
) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR IGNORE INTO incident_mentions (
            incident_id,
            source_id,
            article_id,
            mention_title,
            mention_url,
            published_date
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            incident_id,
            source.id,
            article_id,
            mention_title,
            mention_url,
            published_date,
        ),
    )


def save_incident(conn, source: SourceItem, article_id: int, parsed: dict) -> tuple[int, bool]:
    incident_id = get_incident_id_by_uid(conn, parsed["incident_uid"])
    if incident_id:
        update_existing_incident_geo_if_better(conn, incident_id, parsed, source)
        save_incident_mention(
            conn=conn,
            incident_id=incident_id,
            source=source,
            article_id=article_id,
            mention_title=parsed["title"],
            mention_url=parsed["url"],
            published_date=parsed["published_date"],
        )
        return incident_id, False

    county_value = parsed["county"] or source.county
    city_value = parsed["city"] or source.city
    location_text_value = parsed.get("location_text")
    address_text_value = parsed.get("address_text") or parsed.get("geo_display_name") or parsed.get("geo_query")

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO incidents (
            incident_uid,
            incident_type,
            severity_level,
            title,
            summary,
            event_date,
            published_date,
            days_ago,
            address_text,
            location_text,
            city,
            county,
            latitude,
            longitude,
            geo_confidence,
            ai_confidence,
            is_verified,
            verification_status,
            source_priority,
            duplicate_group_id,
            primary_source_id,
            article_id
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
            address_text_value,
            location_text_value,
            city_value,
            county_value,
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

    incident_id = cursor.lastrowid
    save_incident_mention(
        conn=conn,
        incident_id=incident_id,
        source=source,
        article_id=article_id,
        mention_title=parsed["title"],
        mention_url=parsed["url"],
        published_date=parsed["published_date"],
    )
    return incident_id, True


def should_keep_parsed_result(parsed: dict) -> bool:
    if not parsed.get("title"):
        return False

    if parsed.get("incident_type") == "general":
        return False

    if float(parsed.get("ai_confidence", 0.0)) < MIN_AI_CONFIDENCE:
        return False

    return True


def enrich_parsed_with_source_fallback(parsed: dict, source: SourceItem) -> dict:
    if not parsed.get("county") and source.county:
        parsed["county"] = source.county

    if not parsed.get("city") and source.city:
        parsed["city"] = source.city

    if not parsed.get("geo_query"):
        location_text = parsed.get("location_text")
        city = parsed.get("city")
        county = parsed.get("county")

        parts = []
        if location_text:
            parts.append(location_text)
        if city:
            parts.append(city)
        if county:
            parts.append(county)
        if parts:
            parts.append("romania")
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

                if not should_keep_parsed_result(parsed):
                    stats.articles_skipped_parser += 1
                    continue

                parsed = enrich_parsed_with_source_fallback(parsed, source)

                stats.geocode_attempts += 1
                lat, lng, geo_confidence, geocode_used, geo_display_name = geocode_parsed_incident(
                    session=session,
                    parsed=parsed,
                    source=source,
                )

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
                logger.exception(
                    "Eroare la articol | sursa=%s | url=%s | eroare=%s",
                    source.name,
                    article_url,
                    exc,
                )

    finally:
        conn.close()

    logger.info(
        (
            "Sursa %s | candidate=%s | verificate=%s | pagini_articol=%s | "
            "skip_existing=%s | skip_short=%s | skip_noise=%s | skip_parser=%s | "
            "articole_salvate=%s | incidente_noi=%s | incidente_legare=%s | "
            "geocode_attempts=%s | geocode_success=%s | geocode_failed=%s | erori=%s"
        ),
        source.name,
        stats.candidates_found,
        stats.candidates_checked,
        stats.article_pages_loaded,
        stats.articles_skipped_existing,
        stats.articles_skipped_short,
        stats.articles_skipped_noise,
        stats.articles_skipped_parser,
        stats.articles_saved,
        stats.incidents_saved,
        stats.incidents_linked_existing,
        stats.geocode_attempts,
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

    for source in sources:
        stats = process_source(session, source)
        total.candidates_found += stats.candidates_found
        total.candidates_checked += stats.candidates_checked
        total.article_pages_loaded += stats.article_pages_loaded
        total.articles_skipped_existing += stats.articles_skipped_existing
        total.articles_skipped_short += stats.articles_skipped_short
        total.articles_skipped_noise += stats.articles_skipped_noise
        total.articles_skipped_parser += stats.articles_skipped_parser
        total.articles_saved += stats.articles_saved
        total.incidents_saved += stats.incidents_saved
        total.incidents_linked_existing += stats.incidents_linked_existing
        total.geocode_attempts += stats.geocode_attempts
        total.geocode_success += stats.geocode_success
        total.geocode_failed += stats.geocode_failed
        total.errors += stats.errors

    session.close()

    logger.info(
        (
            "Colectare finalizata | candidate=%s | verificate=%s | pagini_articol=%s | "
            "skip_existing=%s | skip_short=%s | skip_noise=%s | skip_parser=%s | "
            "articole_salvate=%s | incidente_noi=%s | incidente_legare=%s | "
            "geocode_attempts=%s | geocode_success=%s | geocode_failed=%s | erori=%s"
        ),
        total.candidates_found,
        total.candidates_checked,
        total.article_pages_loaded,
        total.articles_skipped_existing,
        total.articles_skipped_short,
        total.articles_skipped_noise,
        total.articles_skipped_parser,
        total.articles_saved,
        total.incidents_saved,
        total.incidents_linked_existing,
        total.geocode_attempts,
        total.geocode_success,
        total.geocode_failed,
        total.errors,
    )


if __name__ == "__main__":
    main()