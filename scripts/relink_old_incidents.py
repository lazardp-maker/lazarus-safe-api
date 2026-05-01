from __future__ import annotations

import re
from collections import defaultdict
from typing import Optional

from app.db import get_connection, get_db_path


MATCH_LOOKBACK_DAYS = 10
MATCH_SCORE_THRESHOLD = 0.62
MAX_TITLE_TOKENS = 12

STOP_TOKENS = {
    "in", "din", "la", "pe", "cu", "de", "si", "și", "un", "o", "a", "au",
    "dintr", "dintr-o", "dintrun", "dintre", "sau", "pentru", "care", "catre",
    "către", "asupra", "caz", "cazul", "privind", "dupa", "după", "ultimele",
    "zile", "luni", "azi", "ieri", "maine", "mâine", "politistii", "polițiștii",
    "politia", "poliția", "arges", "argeș", "bucuresti", "bucurești"
}


def normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""

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


def safe_float(value, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
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


def tokenize_title(value: Optional[str]) -> set[str]:
    text = normalize_text(value)
    tokens = re.findall(r"[a-z0-9]{3,}", text)
    cleaned = [t for t in tokens if t not in STOP_TOKENS]
    return set(cleaned[:MAX_TITLE_TOKENS])


def jaccard_similarity(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    if union == 0:
        return 0.0
    return inter / union


def is_official_source_name(name: Optional[str]) -> bool:
    value = normalize_text(name)
    tokens = ("politia", "ipj", "mai", "isu", "igsu", "dsu", "parchet", "diicot", "jandarmeria")
    return any(token in value for token in tokens)


def fetch_all_incidents() -> list[dict]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                id,
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
                article_id,
                created_at
            FROM incidents
            ORDER BY
                county ASC,
                city ASC,
                incident_type ASC,
                COALESCE(date(event_date), date(published_date), date(created_at)) DESC,
                id DESC
            """
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def fetch_mentions_for_incident(incident_id: int) -> list[dict]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                im.id,
                im.incident_id,
                im.source_id,
                im.article_id,
                im.mention_title,
                im.mention_url,
                im.published_date,
                s.name AS source_name,
                s.source_type AS source_type,
                s.trust_level AS trust_level
            FROM incident_mentions im
            JOIN sources s ON s.id = im.source_id
            WHERE im.incident_id = ?
            ORDER BY
                CASE
                    WHEN s.source_type = 'official' THEN 0
                    WHEN s.source_type = 'press' THEN 1
                    ELSE 2
                END,
                s.trust_level DESC,
                COALESCE(im.published_date, '') DESC,
                s.name ASC
            """,
            (incident_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def compute_match_score(a: dict, b: dict) -> float:
    if normalize_text(a.get("incident_type")) != normalize_text(b.get("incident_type")):
        return 0.0

    score = 0.22

    county_a = normalize_text(a.get("county"))
    county_b = normalize_text(b.get("county"))
    if county_a and county_b and county_a == county_b:
        score += 0.14
    else:
        return 0.0

    city_a = normalize_text(a.get("city"))
    city_b = normalize_text(b.get("city"))
    if city_a and city_b and city_a == city_b:
        score += 0.10
    elif not city_a or not city_b:
        score += 0.03

    date_a = normalize_text(a.get("published_date") or a.get("event_date"))
    date_b = normalize_text(b.get("published_date") or b.get("event_date"))
    if date_a and date_b:
        if date_a == date_b:
            score += 0.16
        else:
            score += 0.04

    loc_a = normalize_text(a.get("location_text") or a.get("address_text"))
    loc_b = normalize_text(b.get("location_text") or b.get("address_text"))
    if loc_a and loc_b:
        if loc_a == loc_b:
            score += 0.18
        elif loc_a in loc_b or loc_b in loc_a:
            score += 0.12

    title_sim = jaccard_similarity(tokenize_title(a.get("title")), tokenize_title(b.get("title")))
    score += min(title_sim * 0.22, 0.22)

    lat_a = safe_float(a.get("latitude"))
    lng_a = safe_float(a.get("longitude"))
    lat_b = safe_float(b.get("latitude"))
    lng_b = safe_float(b.get("longitude"))
    if None not in (lat_a, lng_a, lat_b, lng_b):
        try:
            dist = haversine_meters(lat_a, lng_a, lat_b, lng_b)
            if dist <= 120:
                score += 0.24
            elif dist <= 350:
                score += 0.18
            elif dist <= 800:
                score += 0.10
        except Exception:
            pass

    if safe_int(a.get("is_verified")) == 1 or safe_int(b.get("is_verified")) == 1:
        score += 0.03

    return min(score, 1.0)


class DSU:
    def __init__(self, items: list[dict]):
        self.parent = {item["id"]: item["id"] for item in items}

    def find(self, x: int) -> int:
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, a: int, b: int) -> None:
        ra = self.find(a)
        rb = self.find(b)
        if ra != rb:
            if ra < rb:
                self.parent[rb] = ra
            else:
                self.parent[ra] = rb


def group_candidates(incidents: list[dict]) -> dict[int, list[int]]:
    by_bucket: dict[tuple[str, str, str], list[dict]] = defaultdict(list)

    for item in incidents:
        key = (
            normalize_text(item.get("incident_type")),
            normalize_text(item.get("county")),
            normalize_text(item.get("city")),
        )
        by_bucket[key].append(item)

    dsu = DSU(incidents)

    for _, bucket in by_bucket.items():
        n = len(bucket)
        for i in range(n):
            for j in range(i + 1, n):
                score = compute_match_score(bucket[i], bucket[j])
                if score >= MATCH_SCORE_THRESHOLD:
                    dsu.union(bucket[i]["id"], bucket[j]["id"])

    groups: dict[int, list[int]] = defaultdict(list)
    for item in incidents:
        root = dsu.find(item["id"])
        groups[root].append(item["id"])

    return groups


def choose_master_incident(group_items: list[dict]) -> dict:
    def score(item: dict) -> tuple:
        mentions = fetch_mentions_for_incident(item["id"])
        official_mentions = sum(1 for m in mentions if m.get("source_type") == "official" or is_official_source_name(m.get("source_name")))
        total_mentions = len(mentions)
        verified = safe_int(item.get("is_verified"))
        priority = safe_int(item.get("source_priority"))
        geo = 1 if item.get("latitude") is not None and item.get("longitude") is not None else 0
        ai = safe_float(item.get("ai_confidence"), 0.0) or 0.0
        return (
            official_mentions,
            verified,
            priority,
            geo,
            total_mentions,
            ai,
            -safe_int(item.get("id")),
        )

    return sorted(group_items, key=score, reverse=True)[0]


def select_best_primary_source(incident_ids: list[int]) -> Optional[int]:
    all_mentions: list[dict] = []
    for incident_id in incident_ids:
        all_mentions.extend(fetch_mentions_for_incident(incident_id))

    if not all_mentions:
        return None

    def key(m: dict) -> tuple:
        official = 1 if (m.get("source_type") == "official" or is_official_source_name(m.get("source_name"))) else 0
        trust = safe_int(m.get("trust_level"), 0)
        return (official, trust)

    best = sorted(all_mentions, key=key, reverse=True)[0]
    return safe_int(best.get("source_id"), 0) or None


def merge_group(conn, group_items: list[dict]) -> dict:
    if len(group_items) <= 1:
        return {"merged": 0, "kept": group_items[0]["id"] if group_items else None}

    master = choose_master_incident(group_items)
    master_id = master["id"]
    duplicate_ids = [item["id"] for item in group_items if item["id"] != master_id]

    best_primary_source_id = select_best_primary_source([item["id"] for item in group_items])

    cursor = conn.cursor()

    all_mentions = []
    for item in group_items:
        all_mentions.extend(fetch_mentions_for_incident(item["id"]))

    has_official = any(
        m.get("source_type") == "official" or is_official_source_name(m.get("source_name"))
        for m in all_mentions
    )

    best_source_priority = max(safe_int(item.get("source_priority"), 3) for item in group_items)
    best_ai_confidence = max(safe_float(item.get("ai_confidence"), 0.0) or 0.0 for item in group_items)

    best_geo_item = None
    best_geo_conf = -1.0
    for item in group_items:
        geo_conf = safe_float(item.get("geo_confidence"), -1.0)
        if item.get("latitude") is not None and item.get("longitude") is not None and geo_conf > best_geo_conf:
            best_geo_conf = geo_conf
            best_geo_item = item

    best_location_text = None
    best_address_text = None
    for item in group_items:
        if not best_location_text and item.get("location_text"):
            best_location_text = item.get("location_text")
        if not best_address_text and item.get("address_text"):
            best_address_text = item.get("address_text")

    for dup_id in duplicate_ids:
        cursor.execute(
            """
            UPDATE OR IGNORE incident_mentions
            SET incident_id = ?
            WHERE incident_id = ?
            """,
            (master_id, dup_id),
        )

    cursor.execute(
        """
        UPDATE incidents
        SET
            location_text = COALESCE(?, location_text),
            address_text = COALESCE(?, address_text),
            latitude = COALESCE(?, latitude),
            longitude = COALESCE(?, longitude),
            geo_confidence = CASE
                WHEN ? IS NOT NULL THEN ?
                ELSE geo_confidence
            END,
            ai_confidence = CASE
                WHEN ? > ai_confidence THEN ?
                ELSE ai_confidence
            END,
            is_verified = CASE
                WHEN ? = 1 THEN 1
                ELSE is_verified
            END,
            verification_status = CASE
                WHEN ? = 1 THEN 'verified'
                ELSE verification_status
            END,
            source_priority = CASE
                WHEN ? > source_priority THEN ?
                ELSE source_priority
            END,
            primary_source_id = COALESCE(?, primary_source_id),
            duplicate_group_id = ?
        WHERE id = ?
        """,
        (
            best_location_text,
            best_address_text,
            best_geo_item.get("latitude") if best_geo_item else None,
            best_geo_item.get("longitude") if best_geo_item else None,
            best_geo_item.get("geo_confidence") if best_geo_item else None,
            best_geo_item.get("geo_confidence") if best_geo_item else None,
            best_ai_confidence,
            best_ai_confidence,
            1 if has_official else 0,
            1 if has_official else 0,
            best_source_priority,
            best_source_priority,
            best_primary_source_id,
            f"group-{master_id}",
            master_id,
        ),
    )

    for dup_id in duplicate_ids:
        cursor.execute("DELETE FROM incidents WHERE id = ?", (dup_id,))

    return {"merged": len(duplicate_ids), "kept": master_id, "deleted": duplicate_ids}


def main() -> None:
    print(f"[relink] DB: {get_db_path()}")

    incidents = fetch_all_incidents()
    print(f"[relink] incidente încărcate: {len(incidents)}")

    if not incidents:
        print("[relink] nimic de procesat")
        return

    groups_map = group_candidates(incidents)
    grouped_ids = [ids for ids in groups_map.values() if len(ids) > 1]

    print(f"[relink] grupuri candidate: {len(grouped_ids)}")

    if not grouped_ids:
        print("[relink] nu au fost găsite duplicate probabile")
        return

    incidents_by_id = {item["id"]: item for item in incidents}

    merged_groups = 0
    merged_incidents = 0

    with get_connection() as conn:
        try:
            for ids in grouped_ids:
                group_items = [incidents_by_id[i] for i in ids]
                result = merge_group(conn, group_items)
                if result.get("merged", 0) > 0:
                    merged_groups += 1
                    merged_incidents += result["merged"]
                    print(
                        f"[relink] grup unit | master={result['kept']} | duplicate șterse={result['deleted']}"
                    )

            conn.commit()
        except Exception:
            conn.rollback()
            raise

    print(f"[relink] grupuri unite: {merged_groups}")
    print(f"[relink] incidente duplicate eliminate: {merged_incidents}")
    print("[relink] gata")


if __name__ == "__main__":
    main()