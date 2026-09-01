from __future__ import annotations

import re

from app.discovery.types import DiscoveryCandidate
from app.scanner.url import UrlValidationError, normalize_url

_PHONE = re.compile(r"[^\d+]+")


def normalize_phone(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = _PHONE.sub("", raw.strip())
    return cleaned or None


def normalize_email(raw: str | None) -> str | None:
    if not raw:
        return None
    value = raw.strip().lower()
    if "@" not in value or " " in value:
        return None
    return value[:255]


def normalize_text(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = " ".join(raw.split()).strip()
    return value or None


def normalize_coords(lat: float | None, lon: float | None) -> tuple[float, float] | None:
    if lat is None or lon is None:
        return None
    try:
        latitude = float(lat)
        longitude = float(lon)
    except (TypeError, ValueError):
        return None
    if not (-90.0 <= latitude <= 90.0 and -180.0 <= longitude <= 180.0):
        return None
    return latitude, longitude


def normalize_candidate(raw: DiscoveryCandidate) -> DiscoveryCandidate | None:
    name = normalize_text(raw.name)
    if not name:
        return None
    website_url = None
    if raw.website_url:
        try:
            website_url = normalize_url(raw.website_url).normalized
        except UrlValidationError:
            website_url = None
    coords = normalize_coords(raw.latitude, raw.longitude)
    return DiscoveryCandidate(
        name=name[:255],
        category=normalize_text(raw.category),
        city=normalize_text(raw.city),
        region=normalize_text(raw.region),
        country=normalize_text(raw.country),
        latitude=coords[0] if coords else None,
        longitude=coords[1] if coords else None,
        website_url=website_url,
        phone=normalize_phone(raw.phone),
        email=normalize_email(raw.email),
        source=raw.source or "unknown",
        external_id=normalize_text(raw.external_id),
        extra=raw.extra,
    )
