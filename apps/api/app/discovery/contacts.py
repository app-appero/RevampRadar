from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.config import Settings
from app.discovery.normalize import normalize_email, normalize_phone
from app.scanner.http import scan_http

_EMAIL = re.compile(r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])", re.IGNORECASE)
_CONTACT_HINT = re.compile(r"contatt|contact|email|chi[-\s]?siamo|about|info", re.IGNORECASE)
_MAX_CONTACT_PAGES = 3


def extract_public_email(settings: Settings, website_url: str) -> str | None:
    """Find one public email on the homepage or a same-origin contact page."""
    home = scan_http(website_url, settings)
    if not home.ok or not home.html or not home.final_url:
        return None

    email = _email_in_html(home.html)
    if email:
        return email

    home_origin = urlparse(home.final_url).netloc.casefold()
    contact_urls = _contact_urls(home.html, home.final_url, home_origin)
    for url in contact_urls[: _MAX_CONTACT_PAGES - 1]:
        page = scan_http(url, settings)
        if (
            not page.ok
            or not page.html
            or not page.final_url
            or urlparse(page.final_url).netloc.casefold() != home_origin
        ):
            continue
        email = _email_in_html(page.html)
        if email:
            return email
    return None


def _contact_urls(html: str, page_url: str, origin: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"]).strip()
        label = anchor.get_text(" ", strip=True)
        if not _CONTACT_HINT.search(f"{label} {href}"):
            continue
        url = urljoin(page_url, href)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or parsed.netloc.casefold() != origin:
            continue
        if url not in urls:
            urls.append(url)
            if len(urls) == _MAX_CONTACT_PAGES - 1:
                break
    return urls


def _email_in_html(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"]).strip()
        if href.casefold().startswith("mailto:"):
            email = normalize_email(href[7:].split("?", 1)[0])
            if email:
                return email
    for match in _EMAIL.finditer(soup.get_text(" ", strip=True)):
        email = normalize_email(match.group())
        if email and not email.endswith(("@example.com", "@example.org", "@example.test")):
            return email
    return None


def phone_in_html(html: str) -> str | None:
    """Primo numero esplicito in un link ``tel:`` (nessuna euristica sul testo)."""
    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.find_all("a", href=True):
        href = str(anchor["href"]).strip()
        if href.casefold().startswith("tel:"):
            phone = normalize_phone(href[4:].split("?", 1)[0].replace("%20", ""))
            if phone and sum(ch.isdigit() for ch in phone) >= 6:
                return phone[:64]
    return None


def email_in_html(html: str) -> str | None:
    return _email_in_html(html)
