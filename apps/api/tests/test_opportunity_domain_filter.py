"""GET /opportunities?domain=: dominio esatto del sito, per evitare duplicati prima di POST /companies."""

from __future__ import annotations

import pytest

from app.models.entities import Company, Opportunity, Website


def _company(db, name: str, *, website_url: str | None = None, domain: str | None = None) -> Company:
    company = Company(name=name, source="openstreetmap", status="discovered", website_url=website_url)
    db.add(company)
    db.flush()
    if domain:
        db.add(Website(company_id=company.id, url=website_url or f"https://{domain}",
                       normalized_url=website_url or f"https://{domain}", domain=domain))
    db.add(Opportunity(company_id=company.id, status="discovered", is_favorite=False))
    db.flush()
    return company


@pytest.fixture
def domains(db_session) -> None:
    # Come sul server di sviluppo: dominio salvato con www. e sito http.
    _company(db_session, "Tappezzeria Mazza di Mazza Andrea & C.", website_url="http://www.2-emme.com/",
             domain="www.2-emme.com")
    # Domini simili che NON devono uscire.
    _company(db_session, "Emme Arredi", website_url="https://emme.com/", domain="emme.com")
    _company(db_session, "Negozio 2-emme", website_url="https://shop.2-emme.com/", domain="shop.2-emme.com")
    _company(db_session, "Altro Sito", website_url="https://www.2-emme.com.example.it/")
    _company(db_session, "Senza sito")
    # Solo website_url, senza record Website (capita su 26 aziende in sviluppo).
    _company(db_session, "Hotel Mediterraneo", website_url="http://www.marinahotelpantelleria.com/")
    db_session.commit()


def test_domain_returns_only_tappezzeria_mazza(client, domains) -> None:
    response = client.get("/opportunities", params={"domain": "2-emme.com"})

    assert response.status_code == 200
    assert [item["company_name"] for item in response.json()] == ["Tappezzeria Mazza di Mazza Andrea & C."]
    assert response.headers["x-total-count"] == "1"


@pytest.mark.parametrize(
    "value", ["2-emme.com", "www.2-emme.com", "WWW.2-Emme.COM", "http://www.2-emme.com/chi-siamo", "2-emme.com."]
)
def test_domain_input_is_normalized(client, domains, value: str) -> None:
    names = [item["company_name"] for item in client.get("/opportunities", params={"domain": value}).json()]
    assert names == ["Tappezzeria Mazza di Mazza Andrea & C."]


def test_domain_is_exact_not_substring(client, domains) -> None:
    assert [i["company_name"] for i in client.get("/opportunities", params={"domain": "emme.com"}).json()] == [
        "Emme Arredi"
    ]
    assert [i["company_name"] for i in client.get("/opportunities", params={"domain": "shop.2-emme.com"}).json()] == [
        "Negozio 2-emme"
    ]
    assert client.get("/opportunities", params={"domain": "nessuno.it"}).json() == []


def test_domain_matches_website_url_without_website_record(client, domains) -> None:
    found = client.get("/opportunities", params={"domain": "marinahotelpantelleria.com"}).json()
    assert [item["company_name"] for item in found] == ["Hotel Mediterraneo"]


def test_domain_combines_with_other_filters_and_export(client, domains) -> None:
    assert client.get("/opportunities", params={"domain": "2-emme.com", "status": "contacted"}).json() == []
    exported = client.get("/opportunities/export", params={"domain": "2-emme.com"}).json()
    assert [item["name"] for item in exported["companies"]] == ["Tappezzeria Mazza di Mazza Andrea & C."]


def test_invalid_domain_is_422(client, domains) -> None:
    assert client.get("/opportunities", params={"domain": "non un dominio"}).status_code == 422
