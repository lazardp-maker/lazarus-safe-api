import re
import unicodedata
from datetime import datetime, timezone
from typing import Optional

ROMANIAN_MONTHS = {
    "ianuarie": 1,
    "februarie": 2,
    "martie": 3,
    "aprilie": 4,
    "mai": 5,
    "iunie": 6,
    "iulie": 7,
    "august": 8,
    "septembrie": 9,
    "octombrie": 10,
    "noiembrie": 11,
    "decembrie": 12,
}

COUNTIES = [
    "alba", "arad", "arges", "bacau", "bihor", "bistrita nasaud", "botosani",
    "brasov", "braila", "bucuresti", "buzau", "caras severin", "calarasi",
    "cluj", "constanta", "covasna", "dambovita", "dolj", "galati", "giurgiu",
    "gorj", "harghita", "hunedoara", "ialomita", "iasi", "ilfov", "maramures",
    "mehedinti", "mures", "neamt", "olt", "prahova", "satu mare", "salaj",
    "sibiu", "suceava", "teleorman", "timis", "tulcea", "vaslui", "valcea",
    "vrancea"
]

CITY_HINTS = [
    "pitesti", "mioveni", "curtea de arges", "campulung", "costesti",
    "bucuresti", "cluj napoca", "iasi", "timisoara", "constanta", "brasov",
    "ploiesti", "craiova", "oradea", "arad", "baia mare", "sibiu", "galati",
    "buzau", "satu mare", "targu mures", "focsani", "slatina", "alexandria",
    "vaslui", "botosani", "deva", "resita", "targoviste", "giurgiu"
]

INCIDENT_KEYWORDS = {
    "homicide": [
        "omor", "omucidere", "crima", "crimă", "femicid", "ucis", "ucisa",
        "ucisă", "a fost omorat", "a fost omorât", "si-a ucis", "și-a ucis",
        "lovit mortal", "mort in urma agresiunii", "mort în urma agresiunii"
    ],
    "sexual_violence": [
        "viol", "violat", "violata", "violată", "agresiune sexuala",
        "agresiune sexuală", "abuz sexual", "hartuire sexuala", "hărțuire sexuală",
        "act sexual", "corupere sexuala", "corupere sexuală"
    ],
    "robbery": [
        "talharie", "tâlhărie", "jaf", "jefuit", "jefuita", "jefuita",
        "atacat pentru a-i fura", "deposedat prin violenta", "deposedat prin violență"
    ],
    "theft": [
        "furt", "furat", "furata", "furată", "furturi", "hot", "hoț", "hoti",
        "hoți", "spargere", "a sustras", "a furat", "bunuri sustrase",
        "portofel furat", "telefon furat", "furt din buzunare", "furt din locuinta",
        "furt din locuința", "furt calificat"
    ],
    "violence": [
        "agresiune", "agresiuni", "bataie", "bătaie", "batut", "bătut",
        "batuta", "bătută", "violenta", "violență", "lovire", "ranit", "rănit",
        "conflict violent", "scandal soldat cu violente", "scandal soldat cu violențe"
    ],
    "traffic": [
        "accident rutier", "accident de circulatie", "accident de circulație",
        "coliziune", "a intrat cu masina", "a intrat cu mașina", "rasturnat",
        "răsturnat", "impact intre", "impact între", "autoturism", "masina a lovit",
        "mașina a lovit", "pieton accidentat", "tamponare", "carambol"
    ],
    "emergency": [
        "incendiu", "explozie", "interventia isu", "intervenția isu", "smurd",
        "situatie de urgenta", "situație de urgență", "cutremur", "inundatie",
        "inundație", "alunecare de teren", "copac cazut", "copac căzut",
        "persoana blocata", "persoană blocată"
    ],
    "public_order": [
        "tulburarea ordinii publice", "tulburarea linistii publice",
        "tulburarea liniștii publice", "ordine publica", "ordine publică",
        "scandal public", "huliganism", "grup violent", "deranjarea ordinii"
    ],
}

SEVERITY_KEYWORDS = {
    "high": [
        "decedat", "decedata", "decedată", "mort", "morta", "moarta", "moartă",
        "critic", "grav", "grave", "multiple victime", "cu arma", "cu armă",
        "incendiu puternic", "violenta extrema", "violență extremă",
        "prejudiciu de peste", "retinut pentru omor", "reținut pentru omor"
    ],
    "medium": [
        "ranit", "rănit", "retinut", "reținut", "arestat", "perchezitii",
        "percheziții", "lovit", "internat", "prejudiciu", "dosar penal"
    ],
    "low": [
        "cercetat", "verificari", "verificări", "sanctionat", "sancționat",
        "minor", "tentativa", "tentativă"
    ],
}


def normalize_text(value: Optional[str]) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower().strip()
    value = value.replace("ş", "s").replace("ș", "s")
    value = value.replace("ţ", "t").replace("ț", "t")
    value = re.sub(r"\s+", " ", value)
    return value


def clean_html(raw_html: Optional[str]) -> str:
    if not raw_html:
        return ""
    text = re.sub(r"<script.*?>.*?</script>", " ", raw_html, flags=re.I | re.S)
    text = re.sub(r"<style.*?>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "&")
    text = text.replace("&quot;", '"')
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compact_summary(text: str, max_len: int = 320) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_len:
        return text
    cut = text[:max_len].rsplit(" ", 1)[0].strip()
    return f"{cut}..."


def match_first_keyword(text: str, keywords: list[str]) -> Optional[str]:
    for kw in keywords:
        if kw in text:
            return kw
    return None


def classify_incident_type(title: str, content: str) -> tuple[str, float, Optional[str]]:
    combined = normalize_text(f"{title} {content}")

    best_type = "general"
    best_score = 0.0
    matched_keyword = None

    for incident_type, keywords in INCIDENT_KEYWORDS.items():
        hits = 0
        first_hit = None
        for kw in keywords:
            if kw in combined:
                hits += 1
                if first_hit is None:
                    first_hit = kw

        if hits > 0:
            score = min(0.55 + hits * 0.1, 0.95)
            if score > best_score:
                best_score = score
                best_type = incident_type
                matched_keyword = first_hit

    if best_type == "general":
        return "general", 0.35, None

    return best_type, best_score, matched_keyword


def classify_severity(title: str, content: str, incident_type: str) -> tuple[str, float]:
    combined = normalize_text(f"{title} {content}")

    if incident_type in {"homicide", "sexual_violence"}:
        return "high", 0.92

    for kw in SEVERITY_KEYWORDS["high"]:
        if kw in combined:
            return "high", 0.9

    for kw in SEVERITY_KEYWORDS["medium"]:
        if kw in combined:
            return "medium", 0.75

    for kw in SEVERITY_KEYWORDS["low"]:
        if kw in combined:
            return "low", 0.65

    if incident_type in {"robbery", "violence", "emergency"}:
        return "medium", 0.7
    if incident_type in {"theft", "public_order", "traffic"}:
        return "low", 0.6

    return "low", 0.5


def detect_county(text: str) -> Optional[str]:
    normalized = normalize_text(text)

    for county in COUNTIES:
        if county in normalized:
            return county

    patterns = [
        r"judetul\s+([a-z ]+)",
        r"jud\.\s*([a-z ]+)",
        r"in\s+judetul\s+([a-z ]+)",
        r"din\s+judetul\s+([a-z ]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            candidate = match.group(1).strip()
            for county in COUNTIES:
                if county in candidate or candidate in county:
                    return county

    return None


def detect_city(text: str) -> Optional[str]:
    normalized = normalize_text(text)

    for city in CITY_HINTS:
        if city in normalized:
            return city

    patterns = [
        r"municipiul\s+([a-z ]+)",
        r"orasul\s+([a-z ]+)",
        r"orașul\s+([a-z ]+)",
        r"in\s+([a-z ]+)",
        r"din\s+([a-z ]+)",
        r"la\s+([a-z ]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            candidate = match.group(1).strip()
            candidate = re.sub(r"\b(judet|judetul|jud\.|strada|bulevardul|bd\.|soseaua)\b.*", "", candidate).strip()
            if 2 <= len(candidate) <= 40:
                return candidate

    return None


def extract_published_date(text: str) -> Optional[str]:
    normalized = normalize_text(text)

    iso_match = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", normalized)
    if iso_match:
        year, month, day = iso_match.groups()
        return f"{year}-{month}-{day}"

    dot_match = re.search(r"\b(\d{1,2})[./](\d{1,2})[./](20\d{2})\b", normalized)
    if dot_match:
        day, month, year = dot_match.groups()
        return f"{year}-{int(month):02d}-{int(day):02d}"

    text_month_match = re.search(
        r"\b(\d{1,2})\s+(ianuarie|februarie|martie|aprilie|mai|iunie|iulie|august|septembrie|octombrie|noiembrie|decembrie)\s+(20\d{2})\b",
        normalized
    )
    if text_month_match:
        day, month_name, year = text_month_match.groups()
        month = ROMANIAN_MONTHS[month_name]
        return f"{year}-{month:02d}-{int(day):02d}"

    return None


def compute_days_ago(published_date: Optional[str]) -> Optional[int]:
    if not published_date:
        return None
    try:
        pub = datetime.strptime(published_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now.date() - pub.date()
        return max(delta.days, 0)
    except Exception:
        return None


def build_incident_uid(
    title: str,
    county: Optional[str],
    city: Optional[str],
    incident_type: str,
    published_date: Optional[str]
) -> str:
    source_str = " | ".join([
        normalize_text(title)[:120],
        normalize_text(county),
        normalize_text(city),
        incident_type,
        published_date or "unknown-date",
    ])
    source_str = re.sub(r"[^a-z0-9| -]", "", source_str)
    source_str = re.sub(r"\s+", "-", source_str)
    source_str = source_str.strip("-| ")
    return source_str[:220]


def build_parser_result(
    title: str,
    content: str,
    url: str,
    source_name: str,
) -> dict:
    plain_title = clean_html(title)
    plain_content = clean_html(content)
    combined = f"{plain_title} {plain_content}"

    incident_type, ai_confidence, matched_keyword = classify_incident_type(plain_title, plain_content)
    severity_level, severity_confidence = classify_severity(plain_title, plain_content, incident_type)

    county = detect_county(combined)
    city = detect_city(combined)
    published_date = extract_published_date(combined)
    days_ago = compute_days_ago(published_date)

    summary = compact_summary(plain_content or plain_title, max_len=280)
    incident_uid = build_incident_uid(
        title=plain_title,
        county=county,
        city=city,
        incident_type=incident_type,
        published_date=published_date,
    )

    return {
        "incident_uid": incident_uid,
        "title": plain_title,
        "summary": summary,
        "url": url,
        "source_name": source_name,
        "incident_type": incident_type,
        "severity_level": severity_level,
        "ai_confidence": round((ai_confidence + severity_confidence) / 2, 3),
        "matched_keyword": matched_keyword,
        "county": county,
        "city": city,
        "published_date": published_date,
        "days_ago": days_ago,
        "verification_status": "auto_parsed",
        "is_verified": 0,
        "source_priority": 5 if "politia" in normalize_text(source_name) or "isu" in normalize_text(source_name) or "dsu" in normalize_text(source_name) else 3,
    }