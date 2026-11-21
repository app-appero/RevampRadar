"""GET /companies/match: possibili duplicati con punteggio e normalizzatori."""

from __future__ import annotations

import pytest

from app.models.entities import Company, Opportunity, Website
from app.services.company_match import (
    compact,
    domain_label,
    name_similarity,
    name_tokens,
    normalize_name,
    normalize_phone_it,
)

# --- normalizzatori ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Tappezzeria Mazza di Mazza Andrea & C. S.n.c.", "tappezzeria mazza mazza andrea"),
        ("Ottica Moderna S.R.L.", "ottica moderna"),
        ("OTTICA MODERNA srl", "ottica moderna"),
        ("CEnERE Forno", "cenere forno"),
        ("Tappezzeria d'Arte Antica Prandelli", "tappezzeria arte antica prandelli"),
        ("Caffè Città S.p.A.", "caffe citta"),
        ("Fiori & Piante s.a.s. di Rossi", "fiori piante rossi"),
        ("Società Cooperativa Agricola La Spiga", "agricola spiga"),
    ],
)
def test_normalize_name_drops_legal_form_accents_and_articles(raw: str, expected: str) -> None:
    assert normalize_name(raw) == expected


def test_sector_words_are_not_distinctive() -> None:
    assert name_tokens("Bar Sport") == ["sport"]
    assert name_tokens("CEnERE Forno") == ["cenere"]
    assert name_tokens("Masseria del Piano") == ["piano"]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+39 0363 111111", "0363111111"),
        ("0039 349 577 6033", "3495776033"),
        ("349-5776033", "3495776033"),
        ("+393495776033", "3495776033"),
        ("0363/111111", "0363111111"),
        ("12", None),
        (None, None),
    ],
)
def test_normalize_phone_it(raw, expected) -> None:
    assert normalize_phone_it(raw) == expected


def test_compact_and_domain_label() -> None:
    assert compact("Tappezzeria Prandelli") == "tappezzeriaprandelli"
    assert compact("tappezzeria.prandelli_") == "tappezzeriaprandelli"
    assert domain_label("www.tappezzeriaprandelli.com") == "tappezzeriaprandelli"
    assert domain_label("www.gargidicenere.com") == "gargidicenere"
    assert domain_label("localhost") == ""


def test_name_similarity_needs_a_distinctive_shared_word() -> None:
    assert name_similarity("CEnERE Forno", "Masseria del Piano") == 0.0
    assert name_similarity("Bar Sport", "Bar Centrale") == 0.0  # solo la parola di settore in comune
    assert name_similarity("Tappezzeria Prandelli", "Tappezzeria d'Arte Antica Prandelli") >= 0.5
    assert name_similarity("Ottica Moderna Srl", "OTTICA MODERNA") == 1.0


# --- API -------------------------------------------------------------------------------


@pytest.fixture
def crm(db_session) -> dict[str, Company]:
    def add(name: str, *, city: str | None = None, domain: str | None = None, **fields) -> Company:
        company = Company(name=name, city=city, source="test", status="discovered",
                          website_url=f"https://{domain}/" if domain else None, **fields)
        db_session.add(company)
        db_session.flush()
        if domain:
            db_session.add(Website(company_id=company.id, url=f"https://{domain}/",
                                   normalized_url=f"https://{domain}", domain=domain))
        db_session.add(Opportunity(company_id=company.id, status="discovered", is_favorite=False))
        return company

    # Come sul server di sviluppo.
    created = {
        "cenere": add("CEnERE Forno", city="Bergamo", instagram_handle="cenereforno"),
        "masseria": add("Masseria del Piano", city="Collesano", domain="www.gargidicenere.com"),
        "prandelli": add("Tappezzeria d'Arte Antica Prandelli", city="Brescia",
                         domain="tappezzeriaprandelli.com", instagram_handle="tappezzeriaprandelli"),
        "ottica": add("Ottica Moderna Belluno", city="Belluno", email="otticamoderna9900@libero.it",
                      phone="+390437000111"),
        "bar_vr": add("Bar Sport", city="Verona"),
        "bar_vr2": add("Bar Centrale", city="Verona"),
        "facebook": add("Conviviale Café", city="Verona", domain="www.facebook.com"),
    }
    db_session.commit()
    return created


def _match(client, **params) -> list[dict]:
    response = client.get("/companies/match", params=params)
    assert response.status_code == 200, response.text
    return response.json()["matches"]


def test_cenere_forno_does_not_match_masseria_del_piano(client, crm) -> None:
    """Accettazione: «cenere» nel dominio gargidicenere.com non è una corrispondenza."""
    for params in ({"name": "CEnERE Forno"}, {"name": "CEnERE Forno", "city": "Bergamo"},
                   {"instagram": "cenereforno"}, {"name": "Cenere", "domain": "cenere.it"}):
        names = [item["name"] for item in _match(client, **params)]
        assert "Masseria del Piano" not in names, params
    found = _match(client, name="CEnERE Forno")
    assert found[0]["name"] == "CEnERE Forno"
    assert found[0]["strength"] == "strong"
    assert {item["signal"] for item in found[0]["reasons"]} >= {"name_exact", "name_matches_instagram"}


def test_tappezzeria_prandelli_matches_its_instagram_handle(client, crm) -> None:
    """Accettazione: «Tappezzeria Prandelli» combacia con l'handle tappezzeriaprandelli."""
    by_name = _match(client, name="Tappezzeria Prandelli")
    assert by_name[0]["company_id"] == str(crm["prandelli"].id)
    assert by_name[0]["strength"] == "strong"
    signals = {item["signal"] for item in by_name[0]["reasons"]}
    assert {"name_matches_instagram", "name_matches_domain", "name_similar"} <= signals

    by_handle = _match(client, instagram="@TappezzeriaPrandelli")
    assert by_handle[0]["score"] == 100
    assert by_handle[0]["instagram_handle"] == "tappezzeriaprandelli"
    by_url = _match(client, domain="https://www.tappezzeriaprandelli.com/contatti")
    assert [item["name"] for item in by_url] == ["Tappezzeria d'Arte Antica Prandelli"]


def test_email_phone_and_combined_signals(client, crm) -> None:
    assert _match(client, email="OTTICAMODERNA9900@libero.it")[0]["name"] == "Ottica Moderna Belluno"
    by_phone = _match(client, phone="0437 000111")
    assert by_phone[0]["name"] == "Ottica Moderna Belluno"
    assert by_phone[0]["reasons"][0]["signal"] == "phone"
    both = _match(client, name="Ottica Moderna srl", phone="+39 0437 000111", city="Belluno")
    assert both[0]["score"] > by_phone[0]["score"]


def test_name_only_matches_depend_on_the_city(client, crm) -> None:
    same_city = _match(client, name="Bar Sport", city="Verona")
    assert [item["name"] for item in same_city] == ["Bar Sport"]
    assert "same_city" in {item["signal"] for item in same_city[0]["reasons"]}
    assert _match(client, name="Bar Sport", city="Roma") == []  # stesso nome, altra città: escluso
    assert all(item["name"] != "Bar Centrale" for item in _match(client, name="Bar Sport"))


def test_shared_hosts_are_not_matched_by_domain(client, crm) -> None:
    assert _match(client, domain="https://www.facebook.com/altrapagina") == []
    same_page = _match(client, domain="https://www.facebook.com/")
    assert [item["name"] for item in same_page] == ["Conviviale Café"]


def test_match_requires_an_identifier_and_reports_normalization(client, crm) -> None:
    assert client.get("/companies/match", params={"city": "Verona"}).status_code == 422
    body = client.get("/companies/match", params={"name": "Ottica Moderna S.R.L.", "phone": "+39 0437 000111",
                                                  "instagram": "https://instagram.com/Ottica.Moderna/"}).json()
    assert body["normalized"]["name"] == "ottica moderna"
    assert body["normalized"]["phone"] == "0437000111"
    assert body["normalized"]["instagram"] == "ottica.moderna"
