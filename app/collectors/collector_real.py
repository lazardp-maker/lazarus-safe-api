import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.collectors.parsers import build_parser_result, normalize_text
from app.db import get_connection, get_db_path


REQUEST_TIMEOUT = 15
MAX_LINKS_PER_SOURCE = 80
MAX_ARTICLES_TO_PROCESS = 25
MIN_TITLE_LEN = 18
MIN_CONTENT_LEN = 120
MIN_AI_CONFIDENCE = 0.62

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)


@dataclass
class SourceItem:
    id: int
    name: str
    source_type: str
    base_url: str
    county: Optional[str]
    city: Optional[str]
    trust_level: int


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
        cursor.execute("""
            SELECT id, name, source_type, base_url, county, city, trust_level
            FROM sources
            WHERE is_active = 1
            ORDER BY trust_level DESC, id ASC
        """)
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
            headers={"User-Agent": "Mozilla/5.0 LazarusSafeCollector/3.0"},
        )
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            logging.warning("Continut non-HTML ignorat: %s | %s", url, content_type)
            return None

        response.encoding = response.apparent_encoding
        return response.text
    except requests.RequestException as exc:
        logging.warning("Nu s-a putut accesa %s | %s", url, exc)
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
    blocked_suffixes = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip")
    blocked_fragments = ["javascript:", "mailto:", "/tag/", "/eticheta/", "/categorie/", "/category/"]

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
    seen: set[str] = set()

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

        normalized_key = normalize_text(text)
        if not normalized_key:
            continue

        dedup_key = f"{normalized_key}|{full_url}"
        if dedup_key in seen:
            continue

        seen.add(dedup_key)
        results.append((text, full_url))

    return results[:MAX_LINKS_PER_SOURCE]


def extract_article_content(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")

    title = ""
    if soup.title and soup.title.text:
        title = clean_text(soup.title.text)

    og_title = soup.find("meta", attrs={"property": "og:title"})
    if og_title and og_title.get("content"):
        title = clean_text(og_title["content"])

    paragraphs: list[str] = []
    for p in soup.find_all("p"):
        text = clean_text(p.get_text(" ", strip=True))
        if len(text) >= 35:
            paragraphs.append(text)

    content = " ".join(paragraphs[:30]).strip()
    return title, content


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
            detected_incident_type,
            detected_severity,
            ai_confidence,
            is_processed
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


def save_incident(conn, source: SourceItem, article_id: int, parsed: dict) -> int:
    incident_id = get_incident_id_by_uid(conn, parsed["incident_uid"])
    if incident_id:
        save_incident_mention(
            conn=conn,
            incident_id=incident_id,
            source=source,
            article_id=article_id,
            mention_title=parsed["title"],
            mention_url=parsed["url"],
            published_date=parsed["published_date"],
        )
        return incident_id

    county_value = parsed["county"] or source.county
    city_value = parsed["city"] or source.city

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
            parsed["published_date"],
            parsed["published_date"],
            parsed["days_ago"],
            None,
            None,
            city_value,
            county_value,
            None,
            None,
            None,
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
    return incident_id


def should_keep_parsed_result(parsed: dict) -> bool:
    if not parsed["title"]:
        return False

    if parsed["incident_type"] == "general":
        return False

    if parsed["ai_confidence"] < MIN_AI_CONFIDENCE:
        return False

    return True


def process_source(session: requests.Session, source: SourceItem) -> None:
    logging.info("=== Procesare sursa: %s ===", source.name)

    html = fetch_page(session, source.base_url)
    if not html:
        return

    candidates = extract_candidate_links(html, source.base_url)
    logging.info("Linkuri candidate extrase: %s", len(candidates))

    processed = 0
    saved_articles = 0
    saved_incidents = 0

    conn = get_connection()
    try:
        for link_text, article_url in candidates:
            if processed >= MAX_ARTICLES_TO_PROCESS:
                break

            article_html = fetch_page(session, article_url)
            if not article_html:
                continue

            page_title, article_content = extract_article_content(article_html)
            final_title = page_title if len(page_title) >= MIN_TITLE_LEN else link_text

            combined_text = f"{final_title} {article_content}".strip()

            if len(combined_text) < MIN_CONTENT_LEN:
                continue
            if is_noise(combined_text):
                continue

            parsed = build_parser_result(
                title=final_title,
                content=article_content,
                url=article_url,
                source_name=source.name,
            )

            processed += 1

            if not should_keep_parsed_result(parsed):
                continue

            if not parsed["county"] and source.county:
                parsed["county"] = source.county
            if not parsed["city"] and source.city:
                parsed["city"] = source.city

            article_id = upsert_article(conn, source, parsed)
            saved_articles += 1

            save_incident(conn, source, article_id, parsed)
            saved_incidents += 1

            conn.commit()

            logging.info(
                "SALVAT | %s | %s | %s | conf=%.3f",
                source.name,
                parsed["incident_type"],
                parsed["title"],
                parsed["ai_confidence"],
            )

    except Exception as exc:
        conn.rollback()
        logging.exception("Eroare la procesarea sursei %s: %s", source.name, exc)
    finally:
        conn.close()

    logging.info(
        "Sursa %s | articole procesate: %s | articole salvate: %s | incidente salvate: %s",
        source.name,
        processed,
        saved_articles,
        saved_incidents,
    )


def main() -> None:
    logging.info("Pornire collector_real")
    logging.info("DB: %s", get_db_path())

    sources = get_active_sources()
    logging.info("Surse active incarcate: %s", len(sources))

    if not sources:
        logging.warning("Nu exista surse active in tabela sources.")
        return

    session = requests.Session()
    for source in sources:
        process_source(session, source)

    logging.info("Colectare finalizata.")


if __name__ == "__main__":
    main()