import hashlib
from datetime import datetime, timedelta

from app.db import get_connection, get_db_path


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None

    value = value.strip().lower()
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

    value = " ".join(value.split())
    return value


def build_incident_uid(
    incident_type: str,
    county: str | None,
    city: str | None,
    title: str,
    event_date: str | None,
) -> str:
    raw = "|".join([
        normalize_text(incident_type) or "",
        normalize_text(county) or "",
        normalize_text(city) or "",
        normalize_text(title) or "",
        event_date or "",
    ])
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]
    return f"inc_{digest}"


def iso_days_ago(days_ago: int) -> str:
    return (datetime.utcnow() - timedelta(days=days_ago)).strftime("%Y-%m-%d")


def build_seed_rows():
    raw_incidents = [
        {
            "incident_type": "theft",
            "severity_level": "medium",
            "title": "Furt din autoturism in cartierul Trivale",
            "summary": "Au fost semnalate bunuri sustrase dintr-un autoturism parcat peste noapte.",
            "days_ago": 5,
            "address_text": "Cartier Trivale",
            "location_text": "Pitesti, Arges",
            "city": "pitesti",
            "county": "arges",
            "latitude": 44.8501,
            "longitude": 24.8678,
            "geo_confidence": 0.91,
            "ai_confidence": 0.90,
            "is_verified": 1,
            "verification_status": "verified",
            "source_priority": 5,
        },
        {
            "incident_type": "theft",
            "severity_level": "medium",
            "title": "Furt din locuinta semnalat in zona Gavana",
            "summary": "Politia a fost sesizata privind patrunderea prin efractie intr-o locuinta.",
            "days_ago": 8,
            "address_text": "Gavana",
            "location_text": "Pitesti, Arges",
            "city": "pitesti",
            "county": "arges",
            "latitude": 44.8680,
            "longitude": 24.8460,
            "geo_confidence": 0.88,
            "ai_confidence": 0.91,
            "is_verified": 1,
            "verification_status": "verified",
            "source_priority": 5,
        },
        {
            "incident_type": "robbery",
            "severity_level": "high",
            "title": "Talharie asupra unei persoane in apropierea unei statii de autobuz",
            "summary": "Victima a reclamat deposedarea prin violenta de bunuri personale.",
            "days_ago": 12,
            "address_text": "Zona centrala",
            "location_text": "Pitesti, Arges",
            "city": "pitesti",
            "county": "arges",
            "latitude": 44.8565,
            "longitude": 24.8692,
            "geo_confidence": 0.86,
            "ai_confidence": 0.94,
            "is_verified": 1,
            "verification_status": "verified",
            "source_priority": 5,
        },
        {
            "incident_type": "violence",
            "severity_level": "medium",
            "title": "Conflict spontan intre mai multe persoane intr-o zona publica",
            "summary": "Un conflict izbucnit in spatiul public a necesitat interventia politiei.",
            "days_ago": 15,
            "address_text": "Zona centrala",
            "location_text": "Pitesti, Arges",
            "city": "pitesti",
            "county": "arges",
            "latitude": 44.8572,
            "longitude": 24.8704,
            "geo_confidence": 0.82,
            "ai_confidence": 0.88,
            "is_verified": 1,
            "verification_status": "verified",
            "source_priority": 4,
        },
        {
            "incident_type": "public_order",
            "severity_level": "low",
            "title": "Tulburarea ordinii publice in proximitatea unui local",
            "summary": "Au fost semnalate zgomote si comportament agresiv in timpul noptii.",
            "days_ago": 7,
            "address_text": "Zona Exercitiu",
            "location_text": "Pitesti, Arges",
            "city": "pitesti",
            "county": "arges",
            "latitude": 44.8477,
            "longitude": 24.8782,
            "geo_confidence": 0.80,
            "ai_confidence": 0.84,
            "is_verified": 0,
            "verification_status": "unverified",
            "source_priority": 3,
        },
        {
            "incident_type": "traffic",
            "severity_level": "medium",
            "title": "Accident rutier cu doua autoturisme pe un bulevard intens circulat",
            "summary": "Eveniment rutier soldat cu pagube materiale si trafic ingreunat.",
            "days_ago": 3,
            "address_text": "Bulevard principal",
            "location_text": "Pitesti, Arges",
            "city": "pitesti",
            "county": "arges",
            "latitude": 44.8512,
            "longitude": 24.8790,
            "geo_confidence": 0.89,
            "ai_confidence": 0.90,
            "is_verified": 1,
            "verification_status": "verified",
            "source_priority": 4,
        },
        {
            "incident_type": "emergency",
            "severity_level": "medium",
            "title": "Incendiu izbucnit la o anexa gospodareasca",
            "summary": "Pompierii au intervenit pentru localizarea si stingerea incendiului.",
            "days_ago": 18,
            "address_text": "Zona periferica",
            "location_text": "Mioveni, Arges",
            "city": "mioveni",
            "county": "arges",
            "latitude": 44.9586,
            "longitude": 24.9397,
            "geo_confidence": 0.90,
            "ai_confidence": 0.93,
            "is_verified": 1,
            "verification_status": "verified",
            "source_priority": 5,
        },
        {
            "incident_type": "violence",
            "severity_level": "high",
            "title": "Agresiune fizica in urma unui conflict domestic",
            "summary": "O persoana a avut nevoie de ingrijiri medicale dupa o agresiune.",
            "days_ago": 11,
            "address_text": "Zona rezidentiala",
            "location_text": "Mioveni, Arges",
            "city": "mioveni",
            "county": "arges",
            "latitude": 44.9548,
            "longitude": 24.9370,
            "geo_confidence": 0.87,
            "ai_confidence": 0.92,
            "is_verified": 1,
            "verification_status": "verified",
            "source_priority": 4,
        },
        {
            "incident_type": "homicide",
            "severity_level": "critical",
            "title": "Omor investigat de autoritati intr-o localitate din judet",
            "summary": "Autoritatile desfasoara cercetari intr-un caz de omucidere.",
            "days_ago": 29,
            "address_text": "Localitate rurala",
            "location_text": "Arges",
            "city": None,
            "county": "arges",
            "latitude": None,
            "longitude": None,
            "geo_confidence": None,
            "ai_confidence": 0.95,
            "is_verified": 1,
            "verification_status": "verified",
            "source_priority": 5,
        },
        {
            "incident_type": "sexual_violence",
            "severity_level": "critical",
            "title": "Dosar penal intr-un caz de viol reclamat de victima",
            "summary": "A fost deschis un dosar penal pentru o fapta de violenta sexuala.",
            "days_ago": 34,
            "address_text": "Zona nespecificata",
            "location_text": "Arges",
            "city": None,
            "county": "arges",
            "latitude": None,
            "longitude": None,
            "geo_confidence": None,
            "ai_confidence": 0.94,
            "is_verified": 1,
            "verification_status": "verified",
            "source_priority": 5,
        },
        {
            "incident_type": "theft",
            "severity_level": "low",
            "title": "Tentativa de furt dintr-un magazin de proximitate",
            "summary": "Personalul a sesizat o tentativa de sustragere de produse.",
            "days_ago": 2,
            "address_text": "Zona comerciala",
            "location_text": "Pitesti, Arges",
            "city": "pitesti",
            "county": "arges",
            "latitude": 44.8533,
            "longitude": 24.8751,
            "geo_confidence": 0.85,
            "ai_confidence": 0.86,
            "is_verified": 0,
            "verification_status": "unverified",
            "source_priority": 3,
        },
        {
            "incident_type": "general",
            "severity_level": "low",
            "title": "Interventie a fortelor de ordine intr-o situatie raportata de cetateni",
            "summary": "A fost necesara verificarea unei situatii semnalate telefonic.",
            "days_ago": 9,
            "address_text": "Zona urbana",
            "location_text": "Pitesti, Arges",
            "city": "pitesti",
            "county": "arges",
            "latitude": 44.8581,
            "longitude": 24.8715,
            "geo_confidence": 0.75,
            "ai_confidence": 0.78,
            "is_verified": 0,
            "verification_status": "unverified",
            "source_priority": 3,
        },
    ]

    rows = []
    for item in raw_incidents:
        event_date = iso_days_ago(item["days_ago"])
        published_date = event_date

        incident_uid = build_incident_uid(
            incident_type=item["incident_type"],
            county=item["county"],
            city=item["city"],
            title=item["title"],
            event_date=event_date,
        )

        rows.append((
            incident_uid,
            normalize_text(item["incident_type"]),
            normalize_text(item["severity_level"]),
            item["title"].strip(),
            item["summary"].strip(),
            event_date,
            published_date,
            item["days_ago"],
            item["address_text"],
            item["location_text"],
            normalize_text(item["city"]) if item["city"] else None,
            normalize_text(item["county"]) if item["county"] else None,
            item["latitude"],
            item["longitude"],
            item["geo_confidence"],
            item["ai_confidence"],
            item["is_verified"],
            item["verification_status"],
            item["source_priority"],
            None,
        ))

    return rows


def main() -> None:
    rows = build_seed_rows()

    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.executemany("""
            INSERT OR IGNORE INTO incidents (
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
        """, rows)

        conn.commit()

        cursor.execute("SELECT COUNT(*) AS total FROM incidents")
        total = cursor.fetchone()["total"]

        print("incidents seeded")
        print(f"total incidents in db: {total}")
        print(f"db path: {get_db_path()}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()