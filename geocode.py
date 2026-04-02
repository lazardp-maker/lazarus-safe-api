rom __future__ import annotations

import time
import threading
from typing import Optional, Tuple, Dict, Any

import requests


class GeocodeError(Exception):
    pass


class ReverseGeocoder:
    """
    Reverse geocoding pentru MVP/prototip folosind Nominatim.
    Are:
    - cache in-memory
    - retry scurt
    - normalizare pentru campurile din Romania
    """

    def __init__(
        self,
        user_agent: str = "LazarusSafeAPI/2.0 (contact: admin@lazarus-safe.local)",
        timeout: int = 8,
        max_retries: int = 2,
        cache_ttl_seconds: int = 3600,
    ) -> None:
        self.base_url = "https://nominatim.openstreetmap.org/reverse"
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_retries = max_retries
        self.cache_ttl_seconds = cache_ttl_seconds
        self._cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
        self._lock = threading.Lock()

    def reverse_geocode(self, lat: float, lng: float) -> dict:
        """
        Returneaza dictionar standardizat:
        {
            "county": "arges",
            "city": "pitesti",
            "display_name": "...",
            "raw_address": {...}
        }
        """
        self._validate_coordinates(lat, lng)
        cache_key = self._make_cache_key(lat, lng)

        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        data = self._fetch_reverse(lat, lng)
        parsed = self._parse_nominatim_response(data)

        self._set_cached(cache_key, parsed)
        return parsed

    def reverse_geocode_to_area(self, lat: float, lng: float) -> Tuple[Optional[str], Optional[str]]:
        result = self.reverse_geocode(lat, lng)
        return result.get("county"), result.get("city")

    def _fetch_reverse(self, lat: float, lng: float) -> dict:
        headers = {
            "User-Agent": self.user_agent,
            "Accept-Language": "ro,en",
        }

        params = {
            "format": "jsonv2",
            "lat": lat,
            "lon": lng,
            "zoom": 16,
            "addressdetails": 1,
        }

        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.get(
                    self.base_url,
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
                )

                if response.status_code == 429:
                    # limitare usoara; pauza mica si retry
                    time.sleep(1.2 * attempt)
                    continue

                response.raise_for_status()
                payload = response.json()

                if not isinstance(payload, dict):
                    raise GeocodeError("Răspuns invalid de la serviciul de geocodare.")

                return payload

            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    time.sleep(0.8 * attempt)

        raise GeocodeError(f"Nu s-a putut efectua reverse geocoding: {last_error}")

    def _parse_nominatim_response(self, payload: dict) -> dict:
        address = payload.get("address", {}) or {}
        display_name = payload.get("display_name")

        county_raw = self._pick_first_non_empty(
            address.get("county"),
            address.get("state_district"),
            address.get("region"),
            address.get("state"),
        )

        city_raw = self._pick_first_non_empty(
            address.get("city"),
            address.get("town"),
            address.get("municipality"),
            address.get("village"),
            address.get("hamlet"),
            address.get("suburb"),
            address.get("city_district"),
            address.get("county"),  # fallback slab, dar mai bun decat nimic
        )

        county = self._normalize_county(county_raw)
        city = self._normalize_city(city_raw)

        return {
            "county": county,
            "city": city,
            "display_name": display_name,
            "raw_address": address,
        }

    def _normalize_county(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None

        value = self._normalize_romanian_text(value)

        prefixes = [
            "judetul ",
            "județul ",
            "county ",
            "county of ",
            "districtul ",
            "district ",
            "municipiul ",
        ]

        for prefix in prefixes:
            if value.startswith(prefix):
                value = value[len(prefix):].strip()

        special_map = {
            "municipiul bucuresti": "bucuresti",
            "bucuresti": "bucuresti",
            "bucharest": "bucuresti",
        }

        return special_map.get(value, value)

    def _normalize_city(self, value: Optional[str]) -> Optional[str]:
        if not value:
            return None

        value = self._normalize_romanian_text(value)

        prefixes = [
            "municipiul ",
            "orasul ",
            "orașul ",
            "comuna ",
            "satul ",
            "city of ",
            "city ",
            "town of ",
        ]

        for prefix in prefixes:
            if value.startswith(prefix):
                value = value[len(prefix):].strip()

        aliases = {
            "pitesti": "pitesti",
            "pitești": "pitesti",
            "bucharest": "bucuresti",
        }

        return aliases.get(value, value)

    @staticmethod
    def _normalize_romanian_text(value: str) -> str:
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

        # compactare whitespace
        value = " ".join(value.split())
        return value

    @staticmethod
    def _pick_first_non_empty(*values: Optional[str]) -> Optional[str]:
        for value in values:
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _validate_coordinates(lat: float, lng: float) -> None:
        if not (-90 <= lat <= 90):
            raise GeocodeError("Latitude invalid.")
        if not (-180 <= lng <= 180):
            raise GeocodeError("Longitude invalid.")

    @staticmethod
    def _make_cache_key(lat: float, lng: float) -> str:
        # rotunjire utila pentru a evita requesturi redundante pe coordonate aproape identice
        return f"{round(lat, 5)}:{round(lng, 5)}"

    def _get_cached(self, key: str) -> Optional[dict]:
        now = time.time()
        with self._lock:
            entry = self._cache.get(key)
            if not entry:
                return None

            ts, payload = entry
            if now - ts > self.cache_ttl_seconds:
                del self._cache[key]
                return None

            return payload

    def _set_cached(self, key: str, payload: dict) -> None:
        with self._lock:
            self._cache[key] = (time.time(), payload)


# instanta reutilizabila
_geocoder = ReverseGeocoder()


def reverse_geocode(lat: float, lng: float) -> dict:
    return _geocoder.reverse_geocode(lat, lng)


def reverse_geocode_to_area(lat: float, lng: float) -> Tuple[Optional[str], Optional[str]]:
    return _geocoder.reverse_geocode_to_area(lat, lng)