"""Crawling deterministico e limitato delle pagine prioritarie del sito aziendale.

Nessun crawling illimitato: al massimo MAX_PAGES pagine interne, scelte per URL
riconoscibile (chi-siamo, servizi, prodotti, contatti, storia). Ogni pagina
conserva la propria fonte (URL) per il Company Brief.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.config import Settings
from app.scanner.http import scan_http

MAX_PAGES = 5
MAX_ITEMS_PER_PAGE = 6
MAX_IMAGES_PER_PAGE = 3
_SKIP_IMAGE_HINTS = ("logo", "icon", "sprite", "pixel", "avatar", "badge")

_PAGE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "chi_siamo": (
        "chi-siamo", "chisiamo", "about", "azienda", "storia", "chi-e", "history",
        "la-nostra-storia", "mission", "chi-siete",
    ),
    "servizi": (
        "servizi", "service", "cosa-facciamo", "what-we-do", "cosa-offriamo", "attivita",
    ),
    "prodotti": (
        "prodotti", "product", "catalogo", "catalog", "shop", "store", "menu", "collezione",
    ),
    "contatti": (
        "contatti", "contact", "dove-siamo", "dove-trovarci", "come-contattarci",
    ),
}


@dataclass
class ResearchPage:
    kind: str
    url: str
    title: str | None
    text_excerpt: str
    items: list[dict] = field(default_factory=list)
    images: list[dict] = field(default_factory=list)


def select_priority_pages(internal_links: list[str]) -> list[tuple[str, str]]:
    """Sceglie al massimo MAX_PAGES (kind, url) tra i link interni gia' noti (da un audit)."""
    seen_kinds: set[str] = set()
    selected: list[tuple[str, str]] = []
    for link in internal_links:
        path = urlparse(link).path.lower()
        for kind, keywords in _PAGE_KEYWORDS.items():
            if kind in seen_kinds:
                continue
            if any(keyword in path for keyword in keywords):
                selected.append((kind, link))
                seen_kinds.add(kind)
                break
        if len(selected) >= MAX_PAGES:
            break
    return selected


def fetch_pages(pages: list[tuple[str, str]], settings: Settings) -> list[ResearchPage]:
    results: list[ResearchPage] = []
    for kind, url in pages[:MAX_PAGES]:
        http_result = scan_http(url, settings)
        if not http_result.ok or not http_result.html:
            continue
        soup = BeautifulSoup(http_result.html, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else None
        base_url = http_result.final_url or url
        images = _extract_images(soup, base_url)
        for tag in soup(["script", "style", "nav", "footer", "noscript"]):
            tag.decompose()
        items = _extract_items(soup)
        text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()[:1500]
        results.append(
            ResearchPage(kind=kind, url=url, title=title, text_excerpt=text, items=items, images=images)
        )
    return results


def _extract_images(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """Immagini reali della pagina (og:image + <img> nel contenuto), URL assoluti.
    Esclude loghi/icone/avatar per euristica sul nome file, mai inventate o scaricate qui:
    solo referenziate con il loro URL reale, risolto in assoluto.
    """
    images: list[dict] = []
    seen: set[str] = set()

    og_image = soup.find("meta", property="og:image")
    if og_image and og_image.get("content"):
        images.append({"url": urljoin(base_url, og_image["content"]), "alt": None})
        seen.add(images[0]["url"])

    for img in soup.find_all("img"):
        if len(images) >= MAX_IMAGES_PER_PAGE:
            break
        src = img.get("src") or img.get("data-src")
        if not src or src.startswith("data:"):
            continue
        lowered = src.lower()
        if any(hint in lowered for hint in _SKIP_IMAGE_HINTS):
            continue
        resolved = urljoin(base_url, src)
        if resolved in seen:
            continue
        alt = img.get("alt") or None
        images.append({"url": resolved, "alt": alt.strip() if alt else None})
        seen.add(resolved)

    return images[:MAX_IMAGES_PER_PAGE]


def _extract_items(soup: BeautifulSoup) -> list[dict]:
    """Coppie titolo+estratto da h2/h3 reali della pagina (es. singoli servizi/prodotti
    elencati), cosi' il concept puo' mostrare voci vere invece di segnaposto generici.
    """
    items: list[dict] = []
    for heading in soup.find_all(["h2", "h3"]):
        heading_text = heading.get_text(" ", strip=True)
        if not heading_text or len(heading_text) > 120:
            continue
        body_parts: list[str] = []
        for sibling in heading.find_next_siblings():
            if sibling.name in ("h1", "h2", "h3"):
                break
            text = sibling.get_text(" ", strip=True)
            if text:
                body_parts.append(text)
            if len(" ".join(body_parts)) > 280:
                break
        body = re.sub(r"\s+", " ", " ".join(body_parts)).strip()[:280]
        items.append({"heading": heading_text, "text": body})
        if len(items) >= MAX_ITEMS_PER_PAGE:
            break
    return items
