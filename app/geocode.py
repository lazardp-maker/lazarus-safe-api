from typing import Optional, Tuple
import requests


def normalize_text(value: Optional[str]) -> Optional[str]:
    if not value:
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


def reverse_geocode_real(lat: float, lng: float) -> Tuple[Optional[str], Optional[str]]:
    url = "https://nominatim.openstreetmap.org/reverse"

    headers = {
        "User-Agent": "LazarusSafe/1.0 (contact: lazardp@gmail.com)",
        "Accept": "application/json",
        "Accept-Language": "ro,en",
    }

    params = {
        "lat": lat,
        "lon": lng,
        "format": "jsonv2",
        "addressdetails": 1,
        "zoom": 14,
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        print(f"[geocode] status_code={response.status_code}")
        print(f"[geocode] raw_response={response.text[:1000]}")
        response.raise_for_status()

        data = response.json()
        address = data.get("address", {})

        county = (
            address.get("county")
            or address.get("state_district")
            or address.get("state")
        )

        city = (
            address.get("city")
            or address.get("town")
            or address.get("municipality")
            or address.get("village")
            or address.get("hamlet")
            or address.get("suburb")
            or address.get("city_district")
        )

        county_n = normalize_text(county)
        city_n = normalize_text(city)

        if county_n in {"municipiul bucuresti", "bucharest"}:
            county_n = "bucuresti"

        if city_n in {"municipiul bucuresti", "bucharest"}:
            city_n = "bucuresti"

        print(f"[geocode] county={county} -> {county_n}")
        print(f"[geocode] city={city} -> {city_n}")

        return county_n, city_n

    except Exception as e:
        print(f"[geocode] error={e}")
        return None, None