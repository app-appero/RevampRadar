import httpx

from app.config import Settings
from app.scanner.pagespeed import fetch_pagespeed


def test_no_api_key_returns_none() -> None:
    settings = Settings(pagespeed_api_key="")
    assert fetch_pagespeed("https://example.com", settings) is None


def test_http_error_does_not_leak_api_key_in_error(monkeypatch) -> None:
    def fake_get(url, params=None, timeout=None):
        request = httpx.Request("GET", url, params=params)
        return httpx.Response(403, request=request, text="Forbidden")

    monkeypatch.setattr(httpx, "get", fake_get)
    settings = Settings(pagespeed_api_key="super-secret-key")
    result = fetch_pagespeed("https://example.com", settings)
    assert result is not None
    assert result["ok"] is False
    assert "super-secret-key" not in result["error"]
    assert result["error"] == "pagespeed_http_403"


def test_network_error_does_not_leak_api_key(monkeypatch) -> None:
    def fake_get(url, params=None, timeout=None):
        raise httpx.ConnectError(f"connect failed for {url}?key=super-secret-key")

    monkeypatch.setattr(httpx, "get", fake_get)
    settings = Settings(pagespeed_api_key="super-secret-key")
    result = fetch_pagespeed("https://example.com", settings)
    assert result is not None
    assert result["ok"] is False
    assert "super-secret-key" not in result["error"]
