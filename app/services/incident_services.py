from __future__ import annotations

from typing import Optional

from app.db import get_connection


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

    value = (
        value.replace("județul ", "")
        .replace("judetul ", "")
        .replace("municipiul ", "")
        .replace("orașul ", "")
        .replace("orasul ", "")
        .replace("oraș ", "")
        .replace("oras ", "")
    )

    return value.strip()


def get_recent_incident_counts(
    county: Optional[str] = None,
    city: Optional[str] = None,
    max_days_ago: Optional[int] = 60,
) -> dict:
    conn = get_connection()
    cursor = conn.cursor()

    counts = {
        "homicide": 0,
        "sexual_violence": 0,
        "robbery": 0,
        "theft": 0,
        "violence": 0,
        "traffic": 0,
        "emergency": 0,
        "public_order": 0,
        "general": 0,
    }

    county_n = normalize_text(county) if county else None
    city_n = normalize_text(city) if city else None

    query = """
        SELECT incident_type, COUNT(*) AS total
        FROM incidents
        WHERE 1 = 1
    """
    params: list = []

    if county_n:
        query += " AND county = ?"
        params.append(county_n)

    if city_n:
        query += " AND (city = ? OR city IS NULL)"
        params.append(city_n)

    if max_days_ago is not None:
        query += " AND (days_ago IS NULL OR days_ago <= ?)"
        params.append(max_days_ago)

    query += " GROUP BY incident_type"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    for row in rows:
        incident_type = row["incident_type"]
        total = row["total"]

        if incident_type in counts:
            counts[incident_type] = total
        else:
            counts["general"] += total

    return counts


def get_recent_incidents(
    county: Optional[str] = None,
    city: Optional[str] = None,
    max_days_ago: Optional[int] = 60,
    limit: int = 20,
) -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()

    county_n = normalize_text(county) if county else None
    city_n = normalize_text(city) if city else None

    query = """
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
            created_at,
            updated_at
        FROM incidents
        WHERE 1 = 1
    """
    params: list = []

    if county_n:
        query += " AND county = ?"
        params.append(county_n)

    if city_n:
        query += " AND (city = ? OR city IS NULL)"
        params.append(city_n)

    if max_days_ago is not None:
        query += " AND (days_ago IS NULL OR days_ago <= ?)"
        params.append(max_days_ago)

    query += """
        ORDER BY
            CASE severity_level
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                WHEN 'low' THEN 4
                ELSE 5
            END,
            COALESCE(days_ago, 999999) ASC,
            id DESC
        LIMIT ?
    """
    params.append(limit)

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    incidents: list[dict] = []
    for row in rows:
        incidents.append({
            "id": row["id"],
            "incident_uid": row["incident_uid"],
            "incident_type": row["incident_type"],
            "severity_level": row["severity_level"],
            "title": row["title"],
            "summary": row["summary"],
            "event_date": row["event_date"],
            "published_date": row["published_date"],
            "days_ago": row["days_ago"],
            "address_text": row["address_text"],
            "location_text": row["location_text"],
            "city": row["city"],
            "county": row["county"],
            "latitude": row["latitude"],
            "longitude": row["longitude"],
            "geo_confidence": row["geo_confidence"],
            "ai_confidence": row["ai_confidence"],
            "is_verified": row["is_verified"],
            "verification_status": row["verification_status"],
            "source_priority": row["source_priority"],
            "duplicate_group_id": row["duplicate_group_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        })

    return incidents


def get_recent_incidents_for_display(
    county: Optional[str] = None,
    city: Optional[str] = None,
    max_days_ago: Optional[int] = 60,
    limit: int = 10,
) -> list[dict]:
    incidents = get_recent_incidents(
        county=county,
        city=city,
        max_days_ago=max_days_ago,
        limit=limit,
    )

    display_items: list[dict] = []

    for incident in incidents:
        display_items.append({
            "type": incident["incident_type"],
            "severity": incident["severity_level"],
            "title": incident["title"],
            "summary": incident["summary"],
            "city": incident["city"],
            "county": incident["county"],
            "days_ago": incident["days_ago"],
            "published_date": incident["published_date"],
            "verification_status": incident["verification_status"],
        })

    return display_items


def incident_exists(incident_uid: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 1
        FROM incidents
        WHERE incident_uid = ?
        LIMIT 1
    """, (incident_uid,))
    row = cursor.fetchone()

    conn.close()
    return row is not None


def insert_incident(
    incident_uid: str,
    incident_type: str,
    severity_level: str,
    title: str,
    summary: Optional[str] = None,
    event_date: Optional[str] = None,
    published_date: Optional[str] = None,
    days_ago: Optional[int] = None,
    address_text: Optional[str] = None,
    location_text: Optional[str] = None,
    city: Optional[str] = None,
    county: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    geo_confidence: Optional[float] = None,
    ai_confidence: float = 0.0,
    is_verified: int = 0,
    verification_status: str = "unverified",
    source_priority: int = 3,
    duplicate_group_id: Optional[str] = None,
) -> int:
    conn = get_connection()
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
            duplicate_group_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
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
        normalize_text(city) if city else None,
        normalize_text(county) if county else None,
        latitude,
        longitude,
        geo_confidence,
        ai_confidence,
        is_verified,
        verification_status,
        source_priority,
        duplicate_group_id,
    ))

    new_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return new_id


def upsert_incident(
    incident_uid: str,
    incident_type: str,
    severity_level: str,
    title: str,
    summary: Optional[str] = None,
    event_date: Optional[str] = None,
    published_date: Optional[str] = None,
    days_ago: Optional[int] = None,
    address_text: Optional[str] = None,
    location_text: Optional[str] = None,
    city: Optional[str] = None,
    county: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    geo_confidence: Optional[float] = None,
    ai_confidence: float = 0.0,
    is_verified: int = 0,
    verification_status: str = "unverified",
    source_priority: int = 3,
    duplicate_group_id: Optional[str] = None,
) -> int:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id
        FROM incidents
        WHERE incident_uid = ?
        LIMIT 1
    """, (incident_uid,))
    existing = cursor.fetchone()

    if existing:
        cursor.execute("""
            UPDATE incidents
            SET
                incident_type = ?,
                severity_level = ?,
                title = ?,
                summary = ?,
                event_date = ?,
                published_date = ?,
                days_ago = ?,
                address_text = ?,
                location_text = ?,
                city = ?,
                county = ?,
                latitude = ?,
                longitude = ?,
                geo_confidence = ?,
                ai_confidence = ?,
                is_verified = ?,
                verification_status = ?,
                source_priority = ?,
                duplicate_group_id = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE incident_uid = ?
        """, (
            incident_type,
            severity_level,
            title,
            summary,
            event_date,
            published_date,
            days_ago,
            address_text,
            location_text,
            normalize_text(city) if city else None,
            normalize_text(county) if county else None,
            latitude,
            longitude,
            geo_confidence,
            ai_confidence,
            is_verified,
            verification_status,
            source_priority,
            duplicate_group_id,
            incident_uid,
        ))
        incident_id = existing["id"]
    else:
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
                duplicate_group_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
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
            normalize_text(city) if city else None,
            normalize_text(county) if county else None,
            latitude,
            longitude,
            geo_confidence,
            ai_confidence,
            is_verified,
            verification_status,
            source_priority,
            duplicate_group_id,
        ))
        incident_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return incident_id


def delete_incident_by_uid(incident_uid: str) -> bool:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        DELETE FROM incidents
        WHERE incident_uid = ?
    """, (incident_uid,))

    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()

    return deleted
