import base64

import pytest
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


# --- sessione scaduta: niente finestra di login per le richieste API --------------------

OK_PATH = "/discovery/catalog"  # non usa il database
FETCH = {"Sec-Fetch-Mode": "cors", "Sec-Fetch-Dest": "empty", "Accept": "*/*"}  # fetch('/opportunities')
SAME_ORIGIN_FETCH = {"Sec-Fetch-Mode": "same-origin", "Sec-Fetch-Dest": "empty", "Accept": "*/*"}
NAVIGATION = {
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Dest": "document",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _challenge(response) -> str:
    return response.headers.get("www-authenticate", "")



@pytest.mark.parametrize(
    "headers",
    [FETCH, SAME_ORIGIN_FETCH, {"Accept": "application/json"}, {"X-Requested-With": "XMLHttpRequest"}],
    ids=["fetch-cors", "fetch-same-origin", "accept-json", "x-requested-with"],
)
def test_api_requests_get_json_401_without_basic_challenge(monkeypatch, headers) -> None:
    client = _client(monkeypatch)
    response = client.get("/opportunities", headers=headers)

    assert response.status_code == 401
    assert not _challenge(response).lower().startswith("basic")  # il browser non apre il popup
    assert _challenge(response) == 'xBasic realm="RevampRadar"'
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["code"] == "auth_required"
    assert response.json()["login_url"] == "/auth/login"
    assert response.headers["cache-control"] == "no-store"
    get_settings.cache_clear()


@pytest.mark.parametrize("headers", [NAVIGATION, {}], ids=["browser-page", "curl"])
def test_pages_and_plain_clients_keep_the_basic_challenge(monkeypatch, headers) -> None:
    response = _client(monkeypatch).get("/opportunities", headers=headers)
    assert response.status_code == 401
    assert _challenge(response) == 'Basic realm="RevampRadar"'
    get_settings.cache_clear()


def test_valid_basic_still_passes_for_fetch(monkeypatch) -> None:
    response = _client(monkeypatch).get("/discovery/catalog", headers={**FETCH, **_basic("radar", "s3cret")})
    assert response.status_code == 200
    get_settings.cache_clear()


# --- cookie di sessione ----------------------------------------------------------------


def test_valid_login_sets_long_session_cookie_usable_by_fetch(monkeypatch) -> None:
    client = _client(monkeypatch)
    login = client.get("/discovery/catalog", headers=_basic("radar", "s3cret"))
    cookie = login.headers["set-cookie"]
    assert cookie.startswith("rr_session=")
    for flag in ("HttpOnly", "Secure", "SameSite=Strict", "Path=/", f"Max-Age={720 * 3600}"):
        assert flag in cookie

    token = cookie.split(";")[0].split("=", 1)[1]
    with_cookie = client.get("/discovery/catalog", headers={**FETCH, "Cookie": f"rr_session={token}"})
    assert with_cookie.status_code == 200
    # Cookie ancora fresco: nessun nuovo Set-Cookie a ogni richiesta.
    again = client.get("/discovery/catalog", headers={**_basic("radar", "s3cret"), "Cookie": f"rr_session={token}"})
    assert "set-cookie" not in again.headers
    get_settings.cache_clear()


def test_tampered_or_expired_session_is_rejected_quickly(monkeypatch) -> None:
    import time

    import app.auth as auth_module

    client = _client(monkeypatch)
    token = client.get("/discovery/catalog", headers=_basic("radar", "s3cret")).headers["set-cookie"].split(";")[0]
    expires, signature = token.split("=", 1)[1].split(".")
    forged = f"rr_session={int(expires) + 999}.{signature}"
    assert client.get("/discovery/catalog", headers={**FETCH, "Cookie": forged}).status_code == 401

    real_time = time.time
    monkeypatch.setattr(auth_module.time, "time", lambda: real_time() + 721 * 3600)
    expired = client.get("/opportunities", headers={**FETCH, "Cookie": token})
    assert expired.status_code == 401
    assert _challenge(expired).startswith("xBasic")
    get_settings.cache_clear()


def test_password_change_invalidates_sessions(monkeypatch) -> None:
    token = _client(monkeypatch).get("/discovery/catalog", headers=_basic("radar", "s3cret")).headers["set-cookie"]
    token = token.split(";")[0]
    monkeypatch.setenv("BASIC_AUTH_PASSWORD", "nuova")
    get_settings.cache_clear()
    client = TestClient(create_app(), raise_server_exceptions=False)
    assert client.get("/discovery/catalog", headers={**FETCH, "Cookie": token}).status_code == 401
    get_settings.cache_clear()


def test_session_cookie_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setenv("BASIC_AUTH_SESSION_HOURS", "0")
    response = _client(monkeypatch).get("/discovery/catalog", headers=_basic("radar", "s3cret"))
    assert response.status_code == 200
    assert "set-cookie" not in response.headers
    get_settings.cache_clear()


# --- sessione di lunga durata con rinnovo e /auth/* ---------------------------------------

DAY = 86400


class Clock:
    def __init__(self, monkeypatch) -> None:
        import app.api.auth as auth_api
        import app.auth as auth_module

        self.now = 1_800_000_000.0
        monkeypatch.setattr(auth_module.time, "time", lambda: self.now)
        monkeypatch.setattr(auth_api.time, "time", lambda: self.now)

    def advance(self, days: float) -> None:
        self.now += days * DAY


def _cookie(response) -> str | None:
    raw = response.headers.get("set-cookie")
    return raw.split(";")[0] if raw and raw.startswith("rr_session=") else None


def _status(client, cookie: str | None = None) -> dict:
    headers = {**FETCH, **({"Cookie": cookie} if cookie else {})}
    response = client.get("/auth/status", headers=headers)
    assert response.status_code == 200
    return response.json()


def test_session_lasts_more_than_seven_days_after_login(monkeypatch) -> None:
    clock = Clock(monkeypatch)
    client = _client(monkeypatch)
    login = client.get("/auth/login", headers=_basic("radar", "s3cret"))
    assert login.status_code == 200
    assert login.json()["authenticated"] is True
    assert login.json()["seconds_left"] == 30 * DAY
    cookie = _cookie(login)

    clock.advance(8)  # nessun uso per 8 giorni
    assert client.get(OK_PATH, headers={**FETCH, "Cookie": cookie}).status_code == 200
    clock.advance(23)  # 31 giorni senza rinnovo: scaduta
    expired = client.get(OK_PATH, headers={**FETCH, "Cookie": cookie})
    assert expired.status_code == 401
    assert expired.headers["www-authenticate"].startswith("xBasic")
    get_settings.cache_clear()


def test_every_use_renews_the_session(monkeypatch) -> None:
    clock = Clock(monkeypatch)
    client = _client(monkeypatch)
    cookie = _cookie(client.get("/auth/login", headers=_basic("radar", "s3cret")))

    clock.advance(0.01)  # entro un'ora: nessun nuovo cookie
    assert _cookie(client.get(OK_PATH, headers={**FETCH, "Cookie": cookie})) is None

    clock.advance(20)  # uso dopo 20 giorni: la scadenza riparte da qui
    renewed = _cookie(client.get(OK_PATH, headers={**FETCH, "Cookie": cookie}))
    assert renewed is not None and renewed != cookie
    assert _status(client, renewed)["seconds_left"] == 30 * DAY

    clock.advance(25)  # 45 giorni dal login, 25 dall'ultimo uso: ancora valida
    assert client.get(OK_PATH, headers={**FETCH, "Cookie": renewed}).status_code == 200
    assert client.get(OK_PATH, headers={**FETCH, "Cookie": cookie}).status_code == 401  # il vecchio no
    get_settings.cache_clear()


def test_auth_status_never_blocks_and_explains_the_session(monkeypatch) -> None:
    clock = Clock(monkeypatch)
    client = _client(monkeypatch)
    missing = _status(client)
    assert missing["auth_enabled"] is True
    assert missing["authenticated"] is False
    assert missing["session"] == "missing"
    assert missing["login_url"] == "/auth/login"

    cookie = _cookie(client.get("/auth/login", headers=_basic("radar", "s3cret")))
    valid = _status(client, cookie)
    assert (valid["authenticated"], valid["method"], valid["session"]) == (True, "cookie", "valid")
    assert valid["session_days"] == 30
    clock.advance(1)
    assert _status(client, cookie)["seconds_left"] == 29 * DAY  # lo status non rinnova

    assert _status(client, cookie.replace("rr_session=1", "rr_session=2"))["session"] == "invalid"
    clock.advance(30)
    expired = _status(client, cookie)
    assert (expired["authenticated"], expired["session"]) == (False, "expired")
    get_settings.cache_clear()


def test_login_redirects_only_to_same_site_paths(monkeypatch) -> None:
    client = _client(monkeypatch)
    ok = client.get("/auth/login?next=/opportunities", headers=_basic("radar", "s3cret"), follow_redirects=False)
    assert ok.status_code == 303 and ok.headers["location"] == "/opportunities"
    assert _cookie(ok) is not None
    for target in ("//evil.example/x", "https://evil.example/", "/\\evil.example"):
        response = client.get("/auth/login", params={"next": target}, headers=_basic("radar", "s3cret"),
                              follow_redirects=False)
        assert response.status_code == 200, target
    # Senza credenziali la pagina di login chiede l'accesso (finestra solo da navigazione).
    assert client.get("/auth/login", headers=NAVIGATION).headers["www-authenticate"].startswith("Basic")
    assert client.get("/auth/login", headers=FETCH).headers["www-authenticate"].startswith("xBasic")
    get_settings.cache_clear()


def test_logout_clears_the_cookie(monkeypatch) -> None:
    client = _client(monkeypatch)
    cookie = _cookie(client.get("/auth/login", headers=_basic("radar", "s3cret")))
    response = client.post("/auth/logout", headers={"Cookie": cookie})
    assert response.status_code == 200
    assert "Max-Age=0" in response.headers["set-cookie"]
    get_settings.cache_clear()


def test_auth_status_when_auth_is_disabled(monkeypatch) -> None:
    monkeypatch.delenv("BASIC_AUTH_USER", raising=False)
    monkeypatch.delenv("BASIC_AUTH_PASSWORD", raising=False)
    get_settings.cache_clear()
    body = TestClient(create_app()).get("/auth/status").json()
    assert (body["auth_enabled"], body["authenticated"], body["session"]) == (False, True, "disabled")
    get_settings.cache_clear()

