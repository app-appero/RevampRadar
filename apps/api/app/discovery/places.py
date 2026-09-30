from __future__ import annotations

import math
import re
import unicodedata

import httpx

from app.config import Settings

_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
_FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.location",
        "places.websiteUri",
        "places.internationalPhoneNumber",
    ]
)
_MAX_DISTANCE_M = 300.0
_STOPWORDS = {"hotel", "ristorante", "bar", "srl", "snc", "sas", "di", "da", "del", "della", "il", "la", "e", "the"}


def _tokens(text: str) -> set[str]:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return {t for t in re.findall(r"[a-z0-9]+", folded) if t not in _STOPWORDS}


def _distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def _same_business(name: str, place: dict, latitude: float | None, longitude: float | None) -> bool:
    place_name = (place.get("displayName") or {}).get("text") or ""
    wanted, found = _tokens(name), _tokens(place_name)
    if not wanted or not found or not (wanted & found):
        return False
    loc = place.get("location") or {}
    if latitude is not None and longitude is not None and "latitude" in loc and "longitude" in loc:
        return _distance_m(latitude, longitude, loc["latitude"], loc["longitude"]) <= _MAX_DISTANCE_M
    return True


def find_place(
    settings: Settings,
    api_key: str,
    *,
    name: str,
    city: str | None,
    latitude: float | None,
    longitude: float | None,
) -> dict | None:
    """Cerca l'attività su Google Places (New) e restituisce sito/telefono se il match è credibile.

    Il match richiede almeno una parola del nome in comune e, con coordinate note,
    una distanza entro 300 m: meglio non trovare nulla che attribuire il sito di un omonimo.
    """
    body: dict = {
        "textQuery": f"{name} {city}" if city else name,
        "languageCode": "it",
        "maxResultCount": 5,
    }
    if latitude is not None and longitude is not None:
        body["locationBias"] = {
            "circle": {"center": {"latitude": latitude, "longitude": longitude}, "radius": 500.0}
        }
    headers = {"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": _FIELD_MASK, "Content-Type": "application/json"}
    try:
        with httpx.Client(timeout=httpx.Timeout(settings.discovery_timeout_seconds)) as client:
            response = client.post(_SEARCH_URL, json=body, headers=headers)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Richiesta a Google Places non riuscita: {exc}") from exc
    if response.status_code >= 400:
        try:
            message = response.json().get("error", {}).get("message") or response.text[:300]
        except ValueError:
            message = response.text[:300]
        raise RuntimeError(f"Google Places HTTP {response.status_code}: {message}")
    for place in response.json().get("places") or []:
        if _same_business(name, place, latitude, longitude):
            return {
                "website": place.get("websiteUri"),
                "phone": place.get("internationalPhoneNumber"),
                "place_id": place.get("id"),
            }
    return None
