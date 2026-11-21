"""Link interni rotti nella home: controllo locale, limitato e con protezione SSRF."""

from __future__ import annotations

from urllib.parse import urldefrag, urlparse

import httpx

from app.config import Settings
from app.scanner.http import scanner_client
from app.scanner.ssrf_guard import SSRFBlockedError

_SKIP_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".pdf", ".zip", ".mp4", ".mp3", ".css", ".js")


def internal_page_links(links: list[str], page_url: str, limit: int) -> list[str]:
    """Pagine dello stesso sito (stesso host, www. ignorato), senza ancore, file o duplicati."""
    home = urlparse(page_url)
    home_host = (home.hostname or "").lower().removeprefix("www.")
    home_key = urldefrag(page_url)[0].rstrip("/")
    found: list[str] = []
    for raw in links:
        url = urldefrag(raw)[0]
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().removeprefix("www.")
        if parsed.scheme not in {"http", "https"} or host != home_host:
            continue
        if parsed.path.lower().endswith(_SKIP_EXTENSIONS) or url.rstrip("/") == home_key or url in found:
            continue
        found.append(url)
        if len(found) >= limit:
            break
    return found


def check_links(urls: list[str], settings: Settings, client: httpx.Client | None = None) -> dict:
    """HEAD (GET se il server non lo supporta) su ogni link: 4xx/5xx o irraggiungibile = rotto."""
    own_client = client is None
    http_client = client or scanner_client(settings, timeout=min(6.0, settings.request_timeout_seconds))
    broken: list[dict] = []
    try:
        for url in urls:
            try:
                response = http_client.head(url)
                if response.status_code in {403, 405, 501}:
                    response = http_client.get(url)
                if response.status_code >= 400:
                    broken.append({"url": url, "status": response.status_code})
            except SSRFBlockedError:
                continue
            except httpx.HTTPError as exc:
                broken.append({"url": url, "status": None, "error": exc.__class__.__name__})
    finally:
        if own_client:
            http_client.close()
    return {"checked": len(urls), "broken": broken}
