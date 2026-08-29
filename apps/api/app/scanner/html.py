from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

CTA_PATTERN = re.compile(
    r"contatt|prenot|acquist|scopri|richied|iscriv|cta|buy|book|contact|get started|sign up|quote",
    re.IGNORECASE,
)


@dataclass
class HtmlScanResult:
    title: str | None = None
    meta_description: str | None = None
    h1: list[str] = field(default_factory=list)
    headings: dict[str, int] = field(default_factory=dict)
    canonical: str | None = None
    viewport: str | None = None
    lang: str | None = None
    favicon: str | None = None
    structured_data_count: int = 0
    analytics: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    internal_links: list[str] = field(default_factory=list)
    cta_texts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "meta_description": self.meta_description,
            "h1": self.h1,
            "headings": self.headings,
            "canonical": self.canonical,
            "viewport": self.viewport,
            "lang": self.lang,
            "favicon": self.favicon,
            "structured_data_count": self.structured_data_count,
            "analytics": self.analytics,
            "technologies": self.technologies,
            "internal_links": self.internal_links[:30],
            "cta_texts": self.cta_texts[:20],
        }


def scan_html(html: str, page_url: str) -> HtmlScanResult:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else None
    description_tag = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    meta_description = description_tag.get("content", "").strip() if description_tag else None
    h1 = [node.get_text(" ", strip=True) for node in soup.find_all("h1") if node.get_text(strip=True)]
    headings = {tag: len(soup.find_all(tag)) for tag in ("h1", "h2", "h3", "h4")}
    canonical_tag = soup.find("link", rel=lambda value: value and "canonical" in value)
    canonical = canonical_tag.get("href") if canonical_tag else None
    viewport_tag = soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)})
    viewport = viewport_tag.get("content") if viewport_tag else None
    html_tag = soup.find("html")
    lang = html_tag.get("lang") if html_tag else None
    icon_tag = soup.find("link", rel=lambda value: value and "icon" in value)
    favicon = icon_tag.get("href") if icon_tag else None

    structured_data_count = 0
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        if script.string:
            try:
                json.loads(script.string)
                structured_data_count += 1
            except json.JSONDecodeError:
                continue

    html_lower = html.lower()
    analytics: list[str] = []
    if "googletagmanager.com/gtm.js" in html_lower or "gtm.js" in html_lower:
        analytics.append("google_tag_manager")
    if "google-analytics.com" in html_lower or "gtag(" in html_lower:
        analytics.append("google_analytics")
    if "connect.facebook.net" in html_lower or "fbq(" in html_lower:
        analytics.append("meta_pixel")

    technologies: list[str] = []
    if "wp-content" in html_lower or "wordpress" in html_lower:
        technologies.append("wordpress")
    if "cdn.shopify.com" in html_lower:
        technologies.append("shopify")
    if "__next" in html_lower or "_next/static" in html_lower:
        technologies.append("nextjs")
    elif "data-reactroot" in html_lower:
        technologies.append("react")
    if "ng-version" in html_lower:
        technologies.append("angular")
    if "data-v-" in html_lower or "vue.js" in html_lower:
        technologies.append("vue")

    page_host = urlparse(page_url).netloc
    internal_links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        href = urljoin(page_url, anchor["href"])
        parsed = urlparse(href)
        if parsed.scheme in {"http", "https"} and parsed.netloc == page_host:
            if href not in internal_links:
                internal_links.append(href)
        if len(internal_links) >= 40:
            break

    cta_texts: list[str] = []
    for node in soup.find_all(["a", "button"]):
        text = node.get_text(" ", strip=True)
        if text and CTA_PATTERN.search(text) and text not in cta_texts:
            cta_texts.append(text)
        if len(cta_texts) >= 20:
            break

    return HtmlScanResult(
        title=title or None,
        meta_description=meta_description or None,
        h1=h1,
        headings=headings,
        canonical=canonical,
        viewport=viewport,
        lang=lang,
        favicon=favicon,
        structured_data_count=structured_data_count,
        analytics=analytics,
        technologies=technologies,
        internal_links=internal_links,
        cta_texts=cta_texts,
    )
