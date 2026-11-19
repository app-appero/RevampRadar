"""Canale Instagram di un'azienda: handle normalizzato e data dell'ultimo post.

Le attività senza sito si qualificano spesso solo da Instagram: handle e data dell'ultimo post
vivono in colonne dedicate (filtrabili), non più solo nelle note.
"""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from urllib.parse import urlparse

from app.models.entities import Company

_HANDLE = re.compile(r"^[a-z0-9._]{1,30}$")
_RESERVED_PATHS = frozenset({"p", "reel", "reels", "stories", "explore", "accounts", "tv"})
INSTAGRAM_CHANNELS = frozenset({"ig", "instagram"})


def normalize_instagram_handle(raw: str | None) -> str | None:
    """"@AlbergoMonteCivetta", "instagram.com/albergomontecivetta/" → "albergomontecivetta".

    Restituisce None per un valore vuoto; solleva ValueError se non è un handle valido.
    """
    text = (raw or "").strip()
    if not text:
        return None
    if "instagram.com" in text.lower() or "://" in text:
        parsed = urlparse(text if "://" in text else f"https://{text}")
        host = (parsed.hostname or "").lower().removeprefix("www.").removeprefix("m.")
        parts = [part for part in parsed.path.split("/") if part]
        if host != "instagram.com" or not parts or parts[0].lower() in _RESERVED_PATHS:
            raise ValueError(f"Profilo Instagram non valido: {raw}")
        text = parts[0]
    handle = text.lstrip("@").strip().lower()
    if not _HANDLE.fullmatch(handle) or handle in _RESERVED_PATHS:
        raise ValueError(f"Handle Instagram non valido: {raw} (solo lettere, numeri, punto e _ ; max 30).")
    return handle


def validate_last_post_date(value: date | None, *, today: date | None = None) -> date | None:
    """Una data di ultimo post nel futuro è quasi sempre un errore di battitura."""
    if value is None:
        return None
    limit = (today or datetime.now(UTC).date()) + timedelta(days=1)
    if value > limit:
        raise ValueError(f"Data dell'ultimo post nel futuro: {value.isoformat()}.")
    return value


def instagram_profile_url(handle: str) -> str:
    return f"https://instagram.com/{handle}"


def handle_from_links(links: list[dict[str, str]] | list[tuple[str, str]]) -> str | None:
    """Primo handle Instagram ricavabile da una lista di link social."""
    for item in links:
        url = item.get("url", "") if isinstance(item, dict) else item[1]
        if "instagram.com" not in url.lower():
            continue
        try:
            return normalize_instagram_handle(url)
        except ValueError:
            continue
    return None


def effective_instagram_handle(company: Company | None) -> str | None:
    """Handle salvato oppure ricavato dai link social (inseriti a mano o tag OSM)."""
    if company is None:
        return None
    if company.instagram_handle:
        return company.instagram_handle
    from app.services.pipeline_io import _social_links

    return handle_from_links(_social_links(company))
