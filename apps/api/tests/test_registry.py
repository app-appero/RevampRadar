import httpx

from app.config import Settings
from app.registry.openapi_company import RegistryError, find_company, lookup_by_name, lookup_by_vat

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
                return (
                    httpx.Response(status, json=body, request=httpx.Request("GET", url))
                    if body is not None
                    else httpx.Response(status, request=httpx.Request("GET", url))
                )
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


def test_endpoint(client, monkeypatch) -> None:
    monkeypatch.setattr(httpx, "get", _fake({"IT-advanced/01234567890": (200, {"data": [RAW]})}))
    monkeypatch.setattr("app.api.registry.get_settings", _settings)
    response = client.get("/registry/company", params={"vat": "01234567890"})
    assert response.json()["vat_code"] == "01234567890"
    assert client.get("/registry/company").status_code == 422


def test_find_company_requires_same_city_and_similar_name(monkeypatch) -> None:
    start_ok = {
        "companyName": "PIZZERIA DA MARIO DI ROSSI SNC",
        "vatCode": "111",
        "address": {"registeredOffice": {"town": "Torino"}},
    }
    start_other_city = {
        "companyName": "PIZZERIA DA MARIO",
        "vatCode": "222",
        "address": {"registeredOffice": {"town": "Roma"}},
    }
    monkeypatch.setattr(
        httpx,
        "get",
        _fake(
            {
                "IT-search": (200, {"data": [{"id": "a"}, {"id": "b"}]}),
                "IT-start/a": (200, {"data": [start_other_city]}),
                "IT-start/b": (200, {"data": [start_ok]}),
                "IT-advanced/111": (200, {"data": [RAW]}),
            }
        ),
    )
    assert find_company("Pizzeria Da Mario", "Torino", _settings())["company_name"] == "ACME SRL"
    assert find_company("Ristorante Il Faro", "Torino", _settings()) is None


def test_no_content_means_no_results(monkeypatch) -> None:
    monkeypatch.setattr(httpx, "get", _fake({"IT-search": (204, None)}))
    assert find_company("Nessuna Azienda", "Torino", _settings()) is None


def test_find_company_without_city_refuses_ambiguous_names(monkeypatch) -> None:
    def start(vat, town):
        return {"companyName": "FERRARI SRL", "vatCode": vat, "address": {"registeredOffice": {"town": town}}}

    monkeypatch.setattr(
        httpx,
        "get",
        _fake(
            {
                "IT-search": (200, {"data": [{"id": "a"}, {"id": "b"}]}),
                "IT-start/a": (200, {"data": [start("111", "Modena")]}),
                "IT-start/b": (200, {"data": [start("222", "Roma")]}),
                "IT-advanced/": (200, {"data": [RAW]}),
            }
        ),
    )
    assert find_company("ferrari.com", None, _settings()) is None  # ".com" ignorato, ma due omonimi
    assert find_company("ferrari.com", "Modena", _settings()) is not None
