import httpx
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.registry.openapi_company import RegistryError, lookup_by_name, lookup_by_vat

RAW = {
    "companyName": "ACME SRL",
    "vatCode": "01234567890",
    "taxCode": "01234567890",
    "activityStatus": "ATTIVA",
    "pec": "acme@pec.it",
    "address": {
        "registeredOffice": {
            "streetName": "VIA ROMA 1",
            "town": "MILANO",
            "province": "MI",
            "zipCode": "20100",
            "region": {"description": "LOMBARDIA"},
        }
    },
    "atecoClassification": {"ateco2022": {"code": "62.01", "description": "Software"}},
    "detailedLegalForm": {"description": "SRL"},
    "balanceSheets": {
        "all": [{"year": 2026, "turnover": None, "employees": 3}, {"year": 2024, "turnover": 500000, "employees": 5}]
    },
}


def _settings() -> Settings:
    return Settings(openapi_company_token="secret-token")


def _fake(responses):
    def fake_get(url, params=None, headers=None, timeout=None):
        assert headers["Authorization"] == "Bearer secret-token"
        for suffix, (status, body) in responses.items():
            if suffix in url:
                return httpx.Response(status, json=body, request=httpx.Request("GET", url))
        raise AssertionError(url)

    return fake_get


def test_lookup_by_vat_normalizes(monkeypatch) -> None:
    monkeypatch.setattr(httpx, "get", _fake({"IT-advanced/01234567890": (200, {"data": [RAW]})}))
    data = lookup_by_vat("01234567890", _settings())
    assert data["pec"] == "acme@pec.it"
    assert data["ateco_code"] == "62.01"
    assert data["turnover"] == 500000  # ultimo bilancio con fatturato
    assert data["city"] == "MILANO"


def test_lookup_by_name_resolves_id(monkeypatch) -> None:
    monkeypatch.setattr(
        httpx,
        "get",
        _fake({"IT-search": (200, {"data": [{"id": "abc"}]}), "IT-advanced/abc": (200, {"data": [RAW]})}),
    )
    assert lookup_by_name("acme", _settings())["company_name"] == "ACME SRL"


def test_missing_token_and_http_error_do_not_leak(monkeypatch) -> None:
    try:
        lookup_by_vat("01234567890", Settings(openapi_company_token=""))
    except RegistryError as exc:
        assert str(exc) == "openapi_company_token_missing"
    monkeypatch.setattr(httpx, "get", _fake({"IT-advanced/": (401, {"error": "x"})}))
    try:
        lookup_by_vat("01234567890", _settings())
    except RegistryError as exc:
        assert str(exc) == "openapi_company_http_401"
        assert "secret-token" not in str(exc)


def test_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(httpx, "get", _fake({"IT-advanced/01234567890": (200, {"data": [RAW]})}))
    app = create_app()
    app.dependency_overrides = {}
    monkeypatch.setattr("app.api.registry.get_settings", _settings)
    client = TestClient(app)
    assert client.get("/registry/company", params={"vat": "01234567890"}).json()["vat_code"] == "01234567890"
    assert client.get("/registry/company").status_code == 422
