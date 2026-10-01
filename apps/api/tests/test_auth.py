import base64

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import create_app


def _client(monkeypatch) -> TestClient:
    monkeypatch.setenv("BASIC_AUTH_USER", "radar")
    monkeypatch.setenv("BASIC_AUTH_PASSWORD", "s3cret")
    get_settings.cache_clear()
    return TestClient(create_app(), raise_server_exceptions=False)


def _basic(user: str, password: str) -> dict[str, str]:
    return {"Authorization": "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()}


def test_requests_without_valid_credentials_are_rejected(monkeypatch) -> None:
    client = _client(monkeypatch)
    assert client.get("/settings/ai").status_code == 401
    assert client.get("/settings/ai", headers=_basic("radar", "wrong")).status_code == 401
    assert client.get("/settings/ai", headers={"Authorization": "Basic !!!"}).status_code == 401
    get_settings.cache_clear()


def test_valid_credentials_health_and_preflight_pass(monkeypatch) -> None:
    client = _client(monkeypatch)
    assert client.get("/health").status_code in (200, 503)
    preflight = client.options(
        "/settings/ai",
        headers={
            "Origin": "http://localhost:1420",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert preflight.status_code == 200
    assert client.get("/settings/ai", headers=_basic("radar", "s3cret")).status_code != 401
    get_settings.cache_clear()


def test_auth_disabled_when_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("BASIC_AUTH_USER", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    get_settings.cache_clear()
    assert TestClient(create_app()).get("/health").status_code in (200, 503)
