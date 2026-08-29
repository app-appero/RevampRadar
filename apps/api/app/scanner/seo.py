from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

from app.config import Settings


@dataclass
class SeoScanResult:
    robots_found: bool = False
    robots_url: str | None = None
    sitemap_found: bool = False
    sitemap_url: str | None = None
    noindex: bool = False
    indexable: bool = True

    def to_dict(self) -> dict:
        return {
            "robots_found": self.robots_found,
            "robots_url": self.robots_url,
            "sitemap_found": self.sitemap_found,
            "sitemap_url": self.sitemap_url,
            "noindex": self.noindex,
            "indexable": self.indexable,
        }


def _origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def scan_seo(
    page_url: str,
    html: str | None,
    settings: Settings,
    client: httpx.Client | None = None,
) -> SeoScanResult:
    origin = _origin(page_url)
    robots_url = urljoin(origin + "/", "robots.txt")
    sitemap_url = urljoin(origin + "/", "sitemap.xml")
    timeout = httpx.Timeout(settings.request_timeout_seconds)
    own_client = client is None
    http_client = client or httpx.Client(follow_redirects=True, timeout=timeout)
    result = SeoScanResult(robots_url=robots_url, sitemap_url=sitemap_url)

    try:
        robots = http_client.get(robots_url)
        result.robots_found = robots.status_code == 200 and "text" in robots.headers.get(
            "content-type", "text/plain"
        )
        if result.robots_found and "sitemap:" in robots.text.lower():
            result.sitemap_found = True
        sitemap = http_client.get(sitemap_url)
        if sitemap.status_code == 200 and (
            "xml" in sitemap.headers.get("content-type", "").lower()
            or sitemap.text.lstrip().startswith("<?xml")
            or "<urlset" in sitemap.text.lower()
        ):
            result.sitemap_found = True
    except httpx.HTTPError:
        pass
    finally:
        if own_client:
            http_client.close()

    html_lower = (html or "").lower()
    result.noindex = 'name="robots"' in html_lower and "noindex" in html_lower
    result.indexable = not result.noindex
    return result
