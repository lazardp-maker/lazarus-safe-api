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
    "vrancea",
]

CITY_HINTS = [
    "pitesti", "mioveni", "curtea de arges", "campulung", "costesti",
    "bucuresti", "cluj napoca", "cluj-napoca", "iasi", "timisoara", "constanta",
    "brasov", "ploiesti", "craiova", "oradea", "arad", "baia mare", "sibiu",
    "galati", "buzau", "satu mare", "targu mures", "focsani", "slatina",
    "alexandria", "vaslui", "botosani", "deva", "resita", "targoviste",
    "giurgiu", "piatra neamt", "ramnicu valcea", "alba iulia", "zalau",
    "drobeta turnu severin", "miercurea ciuc", "slobozia", "tulcea",
    "sfantu gheorghe", "voluntari", "suceava", "bacau",
    "ploiesti", "navodari", "medgidia", "tecuci", "lugoj", "petrosani",
    "otopeni", "pantelimon", "buftea", "chitila", "bragadiru",
]

BUCHAREST_SECTOR_PATTERNS = {
    "sector 1": "bucuresti",
    "sector 2": "bucuresti",
    "sector 3": "bucuresti",
    "sector 4": "bucuresti",
    "sector 5": "bucuresti",
    "sector 6": "bucuresti",
}

INCIDENT_KEYWORDS = {
    "homicide": [
        "omor", "omucidere", "crima", "femicid", "ucis", "ucisa",
        "a fost omorat", "a fost omorat", "si-a ucis", "asasinat",
        "lovit mortal", "mort in urma agresiunii",
    ],
    "sexual_violence": [
        "viol", "violat", "violata", "agresiune sexuala",
        "abuz sexual", "hartuire sexuala", "act sexual",
        "corupere sexuala", "violenta sexuala",
    ],
    "robbery": [
        "talharie", "jaf", "jefuit", "deposedat prin violenta",
        "atacat si talharit", "smuls geanta", "smuls lantul",
    ],
    "theft": [
        "furt", "furat", "furata", "furturi", "hot", "hoti",
        "spargere", "a sustras", "a furat", "bunuri sustrase",
        "portofel furat", "telefon furat", "furt din buzunare",
        "furt din locuinta", "furt calificat", "efractie",
        "furt auto", "furt din autoturism",
    ],
    "violence": [
        "agresiune", "agresiuni", "bataie", "batut", "batuta",
        "violenta", "lovire", "ranit", "conflict violent",
        "scandal soldat cu violente", "injunghiat", "injunghiere",
        "altercatie", "scandal", "lovituri",
    ],
    "traffic": [
        "accident rutier", "accident de circulatie",
        "coliziune", "rasturnat", "impact intre",
        "autoturism", "masina a lovit", "pieton accidentat",
        "tamponare", "carambol", "accident pe", "accident in trafic",
    ],
    "emergency": [
        "incendiu", "explozie", "interventia isu", "smurd",
        "situatie de urgenta", "cutremur", "inundatie",
        "alunecare de teren", "copac cazut", "persoana blocata",
        "degajare", "interventie", "apel 112",
    ],
    "public_order": [
        "tulburarea ordinii publice", "tulburarea linistii publice",
        "ordine publica", "scandal public", "huliganism",
        "grup violent", "deranjarea ordinii", "linistea publica",
    ],
}

SEVERITY_KEYWORDS = {
    "critical": [
        "decedat", "decedata", "mort", "morta", "moarta",
        "multiple victime", "in stare critica", "ucis",
        "omorat", "viol", "violata", "violat", "asasinat",
    ],
    "high": [
        "critic", "grav", "grave", "cu arma", "incendiu puternic",
        "violenta extrema", "prejudiciu de peste", "retinut pentru omor",
        "rani grave", "leziuni grave", "agresiune grava",
    ],
    "medium": [
        "ranit", "retinut", "arestat", "perchezitii",
        "lovit", "internat", "prejudiciu", "dosar penal",
        "cercetat penal", "plasat in arest",
    ],
    "low": [
        "cercetat", "verificari", "sanctionat",
        "minor", "tentativa", "suspiciune",
    ],
}

LOCATION_PREFIX_PATTERNS = [
    r"\b(strada|str\.?)\s+[a-z0-9\- ]{2,80}",
    r"\b(bulevardul|bd\.?)\s+[a-z0-9\- ]{2,80}",
    r"\b(calea)\s+[a-z0-9\- ]{2,80}",
    r"\b(soseaua|sos\.?|șoseaua)\s+[a-z0-9\- ]{2,80}",
    r"\b(aleea)\s+[a-z0-9\- ]{2,80}",
    r"\b(piata|piața)\s+[a-z0-9\- ]{2,80}",
    r"\b(cartierul|cartier)\s+[a-z0-9\- ]{2,80}",
    r"\b(zona)\s+[a-z0-9\- ]{2,80}",
    r"\b(intersectia|intersecția)\s+[a-z0-9\- ]{2,120}",
    r"\b(parcul|parc)\s+[a-z0-9\- ]{2,80}",
    r"\b(gara|autogara)\s+[a-z0-9\- ]{0,80}",
    r"\b(dn|dj|a\d{1,2}|e\d{1,3})\s*[- ]?\s*[a-z0-9\- ]{0,60}",
]

STOPWORDS_LOCATION_END = {
    "unde", "dupa", "după", "iar", "care", "cand", "când", "fiind", "pentru",
    "in", "în", "la", "din", "de", "pe", "cu", "si", "și", "un", "o", "a",
    "au", "sau", "prin", "catre", "către",
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

    aliases = {
        "cluj napoca": "cluj-napoca",
        "tirgu mures": "targu mures",
        "bucuresti": "bucuresti",
        "municipiul bucuresti": "bucuresti",
        "orasul bucuresti": "bucuresti",
        "piatra-neamt": "piatra neamt",
        "ramnicu-valcea": "ramnicu valcea",
        "drobeta-turnu severin": "drobeta turnu severin",
        "sfantu-gheorghe": "sfantu gheorghe",
    }

    if value in BUCHAREST_SECTOR_PATTERNS:
        return "bucuresti"

    return aliases.get(value, value)


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


def contains_word(text: str, phrase: str) -> bool:
    pattern = rf"(?<![a-z0-9]){re.escape(normalize_text(phrase))}(?![a-z0-9])"
    return re.search(pattern, normalize_text(text)) is not None


def classify_incident_type(title: str, content: str) -> tuple[str, float, Optional[str]]:
    combined = normalize_text(f"{title} {content}")

    best_type = "general"
    best_score = 0.0
    matched_keyword = None

    for incident_type, keywords in INCIDENT_KEYWORDS.items():
        hits = 0
        first_hit = None

        for kw in keywords:
            kw_n = normalize_text(kw)
            if contains_word(combined, kw_n):
                hits += 1
                if first_hit is None:
                    first_hit = kw

        if hits > 0:
            title_boost = 0.08 if first_hit and contains_word(normalize_text(title), normalize_text(first_hit)) else 0.0
            score = min(0.54 + hits * 0.09 + title_boost, 0.97)
            if score > best_score:
                best_score = score
                best_type = incident_type
                matched_keyword = first_hit

    if best_type == "general":
        return "general", 0.30, None

    return best_type, best_score, matched_keyword


def classify_severity(title: str, content: str, incident_type: str) -> tuple[str, float]:
    combined = normalize_text(f"{title} {content}")

    if incident_type in {"homicide", "sexual_violence"}:
        return "critical", 0.94

    for kw in SEVERITY_KEYWORDS["critical"]:
        if contains_word(combined, kw):
            return "critical", 0.92

    for kw in SEVERITY_KEYWORDS["high"]:
        if contains_word(combined, kw):
            return "high", 0.86

    for kw in SEVERITY_KEYWORDS["medium"]:
        if contains_word(combined, kw):
            return "medium", 0.75

    for kw in SEVERITY_KEYWORDS["low"]:
        if contains_word(combined, kw):
            return "low", 0.64

    if incident_type == "robbery":
        return "high", 0.80
    if incident_type == "violence":
        return "high", 0.76
    if incident_type == "emergency":
        return "high", 0.74
    if incident_type == "theft":
        return "medium", 0.69
    if incident_type == "traffic":
        return "medium", 0.67
    if incident_type == "public_order":
        return "medium", 0.64

    return "low", 0.50


def detect_county(text: str) -> Optional[str]:
    normalized = normalize_text(text)

    for county in COUNTIES:
        pattern = rf"(?<![a-z]){re.escape(county)}(?![a-z])"
        if re.search(pattern, normalized):
            return county

    patterns = [
        r"judetul\s+([a-z ]{2,40})",
        r"jud\.\s*([a-z ]{2,40})",
        r"in\s+judetul\s+([a-z ]{2,40})",
        r"din\s+judetul\s+([a-z ]{2,40})",
        r"in\s+judetul\s+([a-z\- ]{2,40})",
    ]

    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            candidate = match.group(1).strip()
            candidate = re.sub(r"\b(localitatea|orasul|orașul|municipiul|comuna)\b.*", "", candidate).strip()
            for county in COUNTIES:
                if county == candidate or county in candidate or candidate in county:
                    return county

    return None


def detect_bucharest_sector(text: str) -> Optional[str]:
    normalized = normalize_text(text)
    for sector in BUCHAREST_SECTOR_PATTERNS.keys():
        if contains_word(normalized, sector):
            return sector
    return None


def detect_city(text: str) -> Optional[str]:
    normalized = normalize_text(text)

    sector = detect_bucharest_sector(normalized)
    if sector:
        return sector

    for city in CITY_HINTS:
        pattern = rf"(?<![a-z]){re.escape(normalize_text(city))}(?![a-z])"
        if re.search(pattern, normalized):
            return normalize_text(city)

    patterns = [
        r"\bmunicipiul\s+([a-z\- ]{2,60})",
        r"\borasul\s+([a-z\- ]{2,60})",
        r"\borașul\s+([a-z\- ]{2,60})",
        r"\bcomuna\s+([a-z\- ]{2,60})",
        r"\blocalitatea\s+([a-z\- ]{2,60})",
        r"\bsatul\s+([a-z\- ]{2,60})",
        r"\bin\s+([a-z\- ]{2,50})\s+judetul\b",
        r"\bdin\s+([a-z\- ]{2,50})\s+judetul\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            candidate = match.group(1).strip()
            candidate = re.sub(
                r"\b(judet|judetul|jud\.|strada|bulevardul|bd|bd\.|soseaua|sos|sos\.|calea|piata|piața)\b.*",
                "",
                candidate,
            ).strip(" ,-")
            candidate = normalize_text(candidate)

            if candidate and 2 <= len(candidate) <= 50:
                return candidate

    return None


def clean_location_candidate(value: str) -> str:
    value = normalize_text(value)
    value = re.sub(
        r"\b(in care|unde|dupa ce|după ce|care|cand|când|fiindca|fiindcă|iar|si|și)\b.*",
        "",
        value,
    ).strip(" ,-")
    parts = value.split()
    cleaned_parts = []
    for part in parts:
        if part in STOPWORDS_LOCATION_END:
            break
        cleaned_parts.append(part)
    return " ".join(cleaned_parts).strip(" ,-")


def extract_location_phrase(text: str) -> Optional[str]:
    normalized = normalize_text(text)

    for pattern in LOCATION_PREFIX_PATTERNS:
        match = re.search(pattern, normalized)
        if match:
            candidate = clean_location_candidate(match.group(0))
            if 4 <= len(candidate) <= 120:
                return candidate

    context_patterns = [
        r"\bin\s+(zona\s+[a-z0-9\- ]{3,80})",
        r"\bdin\s+(zona\s+[a-z0-9\- ]{3,80})",
        r"\bin\s+(cartierul\s+[a-z0-9\- ]{3,80})",
        r"\bpe\s+(strada\s+[a-z0-9\- ]{3,80})",
        r"\bpe\s+(bulevardul\s+[a-z0-9\- ]{3,80})",
        r"\bpe\s+(calea\s+[a-z0-9\- ]{3,80})",
        r"\bin\s+(piata\s+[a-z0-9\- ]{3,80})",
        r"\bin\s+(intersectia\s+[a-z0-9\- ]{3,100})",
    ]

    for pattern in context_patterns:
        match = re.search(pattern, normalized)
        if match:
            candidate = clean_location_candidate(match.group(1))
            if 4 <= len(candidate) <= 120:
                return candidate

    return None


def build_geo_query(
    location_text: Optional[str],
    city: Optional[str],
    county: Optional[str],
) -> Optional[str]:
    parts = []

    if location_text:
        parts.append(location_text)

    if city:
        parts.append(city)

    if county and county != "bucuresti":
        parts.append(county)

    if county == "bucuresti" and city and city.startswith("sector"):
        parts.append("bucuresti")

    parts.append("romania")

    cleaned = [normalize_text(p) for p in parts if p and normalize_text(p)]
    if not cleaned:
        return None

    deduped = []
    seen = set()
    for item in cleaned:
        if item not in seen:
            seen.add(item)
            deduped.append(item)

    return ", ".join(deduped)


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
        normalized,
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
    published_date: Optional[str],
    location_text: Optional[str] = None,
) -> str:
    source_str = " | ".join([
        normalize_text(title)[:120],
        normalize_text(county),
        normalize_text(city),
        normalize_text(location_text),
        incident_type,
        published_date or "unknown-date",
    ])
    source_str = re.sub(r"[^a-z0-9| -]", "", source_str)
    source_str = re.sub(r"\s+", "-", source_str)
    source_str = source_str.strip("-| ")
    return source_str[:220]


def infer_missing_county_from_city(city: Optional[str]) -> Optional[str]:
    city_n = normalize_text(city)
    city_to_county = {
        "pitesti": "arges",
        "mioveni": "arges",
        "curtea de arges": "arges",
        "campulung": "arges",
        "costesti": "arges",
        "bucuresti": "bucuresti",
        "sector 1": "bucuresti",
        "sector 2": "bucuresti",
        "sector 3": "bucuresti",
        "sector 4": "bucuresti",
        "sector 5": "bucuresti",
        "sector 6": "bucuresti",
        "cluj-napoca": "cluj",
        "iasi": "iasi",
        "timisoara": "timis",
        "constanta": "constanta",
        "brasov": "brasov",
        "ploiesti": "prahova",
        "craiova": "dolj",
        "oradea": "bihor",
        "arad": "arad",
        "baia mare": "maramures",
        "sibiu": "sibiu",
        "galati": "galati",
        "buzau": "buzau",
        "satu mare": "satu mare",
        "targu mures": "mures",
        "focsani": "vrancea",
        "slatina": "olt",
        "alexandria": "teleorman",
        "vaslui": "vaslui",
        "botosani": "botosani",
        "deva": "hunedoara",
        "resita": "caras severin",
        "targoviste": "dambovita",
        "giurgiu": "giurgiu",
        "piatra neamt": "neamt",
        "ramnicu valcea": "valcea",
        "alba iulia": "alba",
        "zalau": "salaj",
        "drobeta turnu severin": "mehedinti",
        "miercurea ciuc": "harghita",
        "slobozia": "ialomita",
        "tulcea": "tulcea",
        "sfantu gheorghe": "covasna",
        "voluntari": "ilfov",
        "suceava": "suceava",
        "bacau": "bacau",
    }
    return city_to_county.get(city_n)


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

    if not county and city:
        county = infer_missing_county_from_city(city)

    if county == "bucuresti" and city and city.startswith("sector"):
        county = "bucuresti"

    location_text = extract_location_phrase(combined)
    geo_query = build_geo_query(
        location_text=location_text,
        city=city,
        county=county,
    )

    published_date = extract_published_date(combined)
    days_ago = compute_days_ago(published_date)

    summary = compact_summary(plain_content or plain_title, max_len=280)
    incident_uid = build_incident_uid(
        title=plain_title,
        county=county,
        city=city,
        incident_type=incident_type,
        published_date=published_date,
        location_text=location_text,
    )

    source_name_n = normalize_text(source_name)
    is_official_source = any(
        token in source_name_n
        for token in ["politia", "isu", "dsu", "igsu", "mai", "ipj", "jandarmeria", "diicot", "parchet"]
    )

    final_confidence = round((ai_confidence + severity_confidence) / 2, 3)

    return {
        "incident_uid": incident_uid,
        "title": plain_title,
        "summary": summary,
        "url": url,
        "source_name": source_name,
        "incident_type": incident_type,
        "severity_level": severity_level,
        "ai_confidence": final_confidence,
        "matched_keyword": matched_keyword,
        "county": county,
        "city": city,
        "location_text": location_text,
        "geo_query": geo_query,
        "published_date": published_date,
        "days_ago": days_ago,
        "verification_status": "verified" if is_official_source else "auto_parsed",
        "is_verified": 1 if is_official_source else 0,
        "source_priority": 5 if is_official_source else 3,
    }