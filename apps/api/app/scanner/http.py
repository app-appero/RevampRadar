from dataclasses import dataclass, field

import httpx

from app.config import Settings
from app.scanner.ssrf_guard import SSRFBlockedError, is_public_hostname

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
    # True: certificato HTTPS valido; False: non valido (pagina letta lo stesso per l'analisi);
    # None: pagina finale in http o non raggiunta.
    tls_valid: bool | None = None
    tls_error: str | None = None

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
            "tls_valid": self.tls_valid,
            "tls_error": self.tls_error,
        }


def _reject_private_targets(request: httpx.Request) -> None:
    """Event hook httpx: valida anche ogni hop di redirect, non solo l'URL iniziale."""
    hostname = request.url.host
    if not hostname or not is_public_hostname(hostname):
        raise SSRFBlockedError(hostname or "")


def _is_tls_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "certificate" in message or "ssl" in message or "tls" in message


def scanner_client(settings: Settings, *, verify: bool = True, timeout: float | None = None) -> httpx.Client:
    """Client dello scanner: redirect limitati e protezione SSRF su ogni hop."""
    headers = {"User-Agent": settings.scanner_user_agent, "Accept": "text/html,application/xhtml+xml"}
    return httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(timeout or settings.request_timeout_seconds),
        headers=headers,
        max_redirects=MAX_REDIRECTS,
        event_hooks={"request": [_reject_private_targets]},
        verify=verify,
    )


def scan_http(url: str, settings: Settings, client: httpx.Client | None = None) -> HttpScanResult:
    """Richiesta alla home. Con certificato non valido la pagina si legge comunque (tls_valid=False):
    le micro-attività hanno spesso il certificato scaduto e sono proprio i prospect da analizzare."""
    own_client = client is None
    http_client = client or scanner_client(settings)
    try:
        result = _scan_with(http_client, url)
    finally:
        if own_client:
            http_client.close()
    if result.error and result.error.startswith("tls_error:") and own_client:
        insecure = scanner_client(settings, verify=False)
        try:
            retried = _scan_with(insecure, url)
        finally:
            insecure.close()
        if retried.ok:
            retried.tls_valid = False
            retried.tls_error = result.error.removeprefix("tls_error:").strip()[:300]
            return retried
    return result


def _scan_with(http_client: httpx.Client, url: str) -> HttpScanResult:
    hostname = httpx.URL(url).host
    if not hostname or not is_public_hostname(hostname):
        return HttpScanResult(ok=False, error="blocked_private_target")
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
            tls_valid=True if str(response.url).startswith("https://") else None,
        )
    except SSRFBlockedError:
        return HttpScanResult(ok=False, error="blocked_private_target")
    except httpx.TooManyRedirects:
        return HttpScanResult(ok=False, error="redirect_loop")
    except httpx.ConnectError as exc:
        if _is_tls_error(exc):
            return HttpScanResult(ok=False, error=f"tls_error: {exc}")
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
