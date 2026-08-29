from dataclasses import dataclass, field

import httpx

from app.config import Settings

MAX_REDIRECTS = 8


@dataclass
class HttpScanResult:
    ok: bool
    final_url: str | None = None
    status_code: int | None = None
    https: bool = False
    redirect_chain: list[str] = field(default_factory=list)
    response_time_ms: int | None = None
    content_type: str | None = None
    page_size_bytes: int | None = None
    html: str | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "final_url": self.final_url,
            "status_code": self.status_code,
            "https": self.https,
            "redirect_chain": self.redirect_chain,
            "response_time_ms": self.response_time_ms,
            "content_type": self.content_type,
            "page_size_bytes": self.page_size_bytes,
            "error": self.error,
        }


def scan_http(url: str, settings: Settings, client: httpx.Client | None = None) -> HttpScanResult:
    headers = {"User-Agent": settings.scanner_user_agent, "Accept": "text/html,application/xhtml+xml"}
    timeout = httpx.Timeout(settings.request_timeout_seconds)
    own_client = client is None
    http_client = client or httpx.Client(
        follow_redirects=True,
        timeout=timeout,
        headers=headers,
        max_redirects=MAX_REDIRECTS,
    )
    try:
        response = http_client.get(url)
        chain = [str(item.url) for item in response.history] + [str(response.url)]
        content_type = response.headers.get("content-type")
        html = None
        if content_type and "html" in content_type.lower():
            html = response.text
        elif not content_type and response.text.lstrip().lower().startswith("<"):
            html = response.text
        return HttpScanResult(
            ok=True,
            final_url=str(response.url),
            status_code=response.status_code,
            https=str(response.url).startswith("https://"),
            redirect_chain=chain,
            response_time_ms=int(response.elapsed.total_seconds() * 1000),
            content_type=content_type,
            page_size_bytes=len(response.content),
            html=html,
        )
    except httpx.TooManyRedirects:
        return HttpScanResult(ok=False, error="redirect_loop")
    except httpx.ConnectError as exc:
        message = str(exc).lower()
        code = (
            "dns_error"
            if "name or service not known" in message or "getaddrinfo" in message
            else "connection_error"
        )
        return HttpScanResult(ok=False, error=code)
    except httpx.TimeoutException:
        return HttpScanResult(ok=False, error="timeout")
    except httpx.HTTPError as exc:
        return HttpScanResult(ok=False, error=str(exc) or "http_error")
    finally:
        if own_client:
            http_client.close()
