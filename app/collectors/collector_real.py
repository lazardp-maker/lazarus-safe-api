import hashlib
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from app.db import get_connection, get_db_path


REQUEST_TIMEOUT = 12
MAX_LINKS_PER_SOURCE = 60
MAX_ARTICLES_TO_PROCESS = 20
MIN_TITLE_LEN = 20
MIN_CONTENT_LEN = 80

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)


@dataclass
class SourceItem:
    id: int
    name: str
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
    "situatii de urgenta",
    "situații de urgență",
    "cumpara in siguranta",
    "cumpără în siguranță",
    "prioritatea politistilor",
    "prioritatea polițiștilor",
    "plan de management",
    "actiune integrata",
    "acțiune integrată",
    "transparentei intereselor",
]

INCIDENT_RULES = {
    "homicide": {
        "severity": "high",
        "keywords": [
            "omor", "omorat", "omorare",
            "omucidere", "ucis", "ucisa",
            "a fost ucis", "fost ucisa", "fost ucis",
            "femicid", "crima", "crimă", "asasinat",
            "mort in urma agresiunii", "mort în urma agresiunii",
        ],
    },
    "sexual_violence": {
        "severity": "critical",
        "keywords": [
            "viol", "violat", "violata", "violată", "violator",
            "agresiune sexuala", "agresiune sexuală",
            "abuz sexual", "act sexual",
            "trafic de persoane", "exploatare sexuala", "exploatare sexuală",
        ],
    },
    "robbery": {
        "severity": "high",
        "keywords": [
            "talhar", "tâlhar", "talharie", "tâlhărie",
            "jaf", "jefuit", "jefuire",
        ],
    },
    "theft": {
        "severity": "medium",
        "keywords": [
            "furt", "furturi", "hot", "hoț", "hoti", "hoți",
            "buzunare", "buzunar", "sustras", "sustragere",
            "spargere", "a furat", "au furat",
        ],
    },
    "violence": {
        "severity": "high",
        "keywords": [
            "agresiune", "agresiuni", "lovire", "loviri",
            "bataie", "bătaie", "batai", "bătăi",
            "atac", "conflict violent", "scandal violent",
            "injunghiat", "înjunghiat", "injunghiere", "înjunghiere",
            "arme albe", "arma alba", "armă albă",
        ],
    },
    "traffic": {
        "severity": "medium",
        "keywords": [
            "accident", "accident rutier", "coliziune", "impact",
            "autoturism", "autovehicul",
            "ranit", "rănit", "raniti", "răniți",
            "decedat in accident", "decedat în accident",
            "pieton", "tamponare",
        ],
    },
    "emergency": {
        "severity": "high",
        "keywords": [
            "incendiu", "incendii", "explozie",
            "flacari", "flăcări", "ardere", "a luat foc",
            "fum dens", "interventia pompierilor", "intervenția pompierilor",
        ],
    },
    "public_order": {
        "severity": "low",
        "keywords": [
            "tulburarea ordinii publice",
            "tulburarea linistii publice",
            "tulburarea liniștii publice",
            "ordine publica",
            "ordine publică",
            "scandal",
        ],
    },
}


def normalize_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    value = value.lower().strip()
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

    return " ".join(value.split())


def clean_text(text: str) -> str:
    return " ".join(text.split()).strip()


def get_active_sources() -> list[SourceItem]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, base_url, county, city, trust_level
            FROM sources
            WHERE is_active = 1
            ORDER BY trust_level DESC, id ASC
        """)
        rows = cursor.fetchall()

        return [
            SourceItem(
                id=row["id"],
                name=row["name"],
                base_url=row["base_url"],
                county=normalize_text(row["county"]),
                city=normalize_text(row["city"]),
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
            headers={"User-Agent": "Mozilla/5.0 LazarusSafeCollector/2.0"},
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


def classify_incident(text: str) -> tuple[Optional[str], Optional[str]]:
    t = normalize_text(text) or ""
    for incident_type, config in INCIDENT_RULES.items():
        if any(keyword in t for keyword in config["keywords"]):
            return incident_type, config["severity"]
    return None, None


def same_domain(base_url: str, candidate_url: str) -> bool:
    base_netloc = urlparse(base_url).netloc.lower().replace("www.", "")
    cand_netloc = urlparse(candidate_url).netloc.lower().replace("www.", "")
    return base_netloc == cand_netloc


def is_valid_article_url(url: str) -> bool:
    if not url:
        return False
    lowered = url.lower()
    if lowered.startswith("javascript:"):
        return False
    if lowered.startswith("mailto:"):
        return False
    if "#" in lowered and lowered.endswith("#"):
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

    paragraphs = []
    for p in soup.find_all("p"):
        text = clean_text(p.get_text(" ", strip=True))
        if len(text) >= 30:
            paragraphs.append(text)

    content = " ".join(paragraphs[:20]).strip()
    return title, content


def build_incident_uid(source_id: int, article_url: str, title: str) -> str:
    raw = f"{source_id}|{article_url}|{normalize_text(title)}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def incident_exists(incident_uid: str) -> bool:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 1
            FROM incidents
            WHERE incident_uid = ?
            LIMIT 1
        """, (incident_uid,))
        row = cursor.fetchone()
        return row is not None
    finally:
        conn.close()


def save_incident(
    source: SourceItem,
    title: str,
    article_url: str,
    article_content: str,
    incident_type: str,
    severity_level: str,
) -> None:
    incident_uid = build_incident_uid(source.id, article_url, title)

    if incident_exists(incident_uid):
        logging.info("EXISTA DEJA | %s | %s", source.name, title)
        return

    now_iso = datetime.now(timezone.utc).isoformat()

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
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
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            incident_uid,
            incident_type,
            severity_level,
            title,
            article_content[:1500] if article_content else title,
            None,
            now_iso,
            0,
            None,
            article_url,
            source.city,
            source.county,
            None,
            None,
            None,
            0.82,
            0,
            "detected_by_rules",
            source.trust_level,
            None,
            now_iso,
            now_iso,
        ))
        conn.commit()
        logging.info("SALVAT | %s | %s | %s", source.name, incident_type, title)
    except sqlite3.IntegrityError as exc:
        logging.warning("Duplicate/integrity error | %s | %s", title, exc)
    finally:
        conn.close()


def process_source(session: requests.Session, source: SourceItem) -> None:
    logging.info("=== Procesare sursa: %s ===", source.name)

    html = fetch_page(session, source.base_url)
    if not html:
        return

    candidates = extract_candidate_links(html, source.base_url)
    logging.info("Linkuri candidate extrase: %s", len(candidates))

    processed = 0
    incident_count = 0

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

        incident_type, severity = classify_incident(combined_text)
        processed += 1

        if not incident_type or not severity:
            continue

        incident_count += 1
        logging.info("INCIDENT [%s / %s] %s | %s", incident_type, severity, source.name, final_title)

        save_incident(
            source=source,
            title=final_title,
            article_url=article_url,
            article_content=article_content,
            incident_type=incident_type,
            severity_level=severity,
        )

    logging.info(
        "Sursa %s | articole procesate: %s | incidente detectate: %s",
        source.name, processed, incident_count
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