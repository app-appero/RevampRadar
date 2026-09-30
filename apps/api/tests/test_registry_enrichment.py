import httpx
import pytest

from app.config import Settings
from app.models.entities import BusinessSignal, Company
from app.services.ai_settings import is_openapi_available, update_ai_credentials
from app.services.registry_enrichment import EnrichmentError, enrich_from_registry
from tests.test_registry import RAW, _fake


def _company(db_session) -> Company:
    company = Company(name="ACME SRL", city="Milano", source="test")
    db_session.add(company)
    db_session.commit()
    return company


def test_token_saved_in_settings_is_used(db_session, monkeypatch) -> None:
    company = _company(db_session)
    base = Settings(openapi_company_token="")
    with pytest.raises(EnrichmentError) as exc:
        enrich_from_registry(db_session, company.id, base, vat="01234567890")
    assert exc.value.status_code == 503

    update_ai_credentials(
        db_session, provider=None, anthropic_api_key=None, openai_api_key=None, openapi_company_token="secret-token"
    )
    assert is_openapi_available(db_session, base) is True
    monkeypatch.setattr(httpx, "get", _fake({"IT-advanced/01234567890": (200, {"data": [RAW]})}))
    saved = enrich_from_registry(db_session, company.id, base, vat="01234567890")
    keys = {(s.key, s.period) for s in saved}
    assert ("revenue", "2024") in keys and ("employees", "2024") in keys and ("legal_form", "") in keys
    assert all(s.confidence == "verified" and not s.is_manual for s in saved)


def test_manual_signals_are_not_overwritten(db_session, monkeypatch) -> None:
    company = _company(db_session)
    db_session.add(
        BusinessSignal(
            company_id=company.id,
            key="legal_form",
            period="",
            label="Forma",
            value="MANUALE",
            source="io",
            confidence="manual",
            is_manual=True,
        )
    )
    db_session.commit()
    monkeypatch.setattr(httpx, "get", _fake({"IT-advanced/01234567890": (200, {"data": [RAW]})}))
    enrich_from_registry(db_session, company.id, Settings(openapi_company_token="secret-token"), vat="01234567890")
    row = db_session.query(BusinessSignal).filter_by(key="legal_form").one()
    assert row.value == "MANUALE"


def test_no_match_is_404(db_session, monkeypatch) -> None:
    company = _company(db_session)
    monkeypatch.setattr(httpx, "get", _fake({"IT-search": (200, {"data": []})}))
    with pytest.raises(EnrichmentError) as exc:
        enrich_from_registry(db_session, company.id, Settings(openapi_company_token="secret-token"))
    assert exc.value.status_code == 404


def test_enrichment_endpoint(client, db_session, monkeypatch) -> None:
    company = _company(db_session)
    monkeypatch.setattr(httpx, "get", _fake({"IT-advanced/01234567890": (200, {"data": [RAW]})}))
    monkeypatch.setattr("app.api.deep_research.get_settings", lambda: Settings(openapi_company_token="secret-token"))
    response = client.post(f"/companies/{company.id}/registry-enrichment", json={"vat": "01234567890"})
    assert response.status_code == 200
    assert {item["key"] for item in response.json()} >= {"revenue", "employees"}
    listed = client.get(f"/companies/{company.id}/business-signals").json()
    assert any(item["key"] == "revenue" and item["confidence"] == "verified" for item in listed)
