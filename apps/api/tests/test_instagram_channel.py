"""Canale Instagram: instagram_handle e instagram_last_post_at, filtri channel/last_post_after, ricerca q."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models.entities import Company, Opportunity, Website


def _post(client, **body):
    return client.post("/companies", json={"city": "Treviso", **body})


# --- POST /companies --------------------------------------------------------------------


def test_create_with_handle_and_last_post_date(client) -> None:
    response = _post(
        client,
        name="Panificio Al Forno",
        instagram_handle="@Panificio.AlForno",
        instagram_last_post_at="2026-11-12",
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["outcome"] == "created"
    assert body["company"]["instagram_handle"] == "panificio.alforno"
    assert body["company"]["instagram_last_post_at"] == "2026-11-12"
    # Il profilo entra anche fra i social, così la deduplica per social lo riconosce.
    assert {"label": "Instagram", "url": "https://instagram.com/panificio.alforno"} in body["company"]["social_links"]

    detail = client.get(f"/opportunities/{body['opportunity_id']}").json()
    assert detail["instagram_handle"] == "panificio.alforno"
    assert detail["instagram_last_post_at"] == "2026-11-12"
    company = client.get(f"/companies/{body['company_id']}").json()
    assert company["instagram_last_post_at"] == "2026-11-12"


@pytest.mark.parametrize(
    "raw", ["panificio.alforno", "@panificio.alforno", "https://www.instagram.com/panificio.alforno/",
            "instagram.com/Panificio.AlForno?igsh=abc"],
)
def test_handle_forms_are_normalized(client, raw: str) -> None:
    body = _post(client, name="Panificio Al Forno", instagram_handle=raw).json()
    assert body["company"]["instagram_handle"] == "panificio.alforno"


def test_handle_is_derived_from_instagram_social_link(client) -> None:
    body = _post(
        client,
        name="Fiori di Lia",
        social_links=[{"label": "Instagram", "url": "https://www.instagram.com/fioridilia/"}],
        instagram_last_post_at="2026-11-01",
    ).json()
    assert body["company"]["instagram_handle"] == "fioridilia"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("instagram_handle", "non valido con spazi"),
        ("instagram_handle", "https://www.instagram.com/p/C0abc/"),
        ("instagram_handle", "https://facebook.com/pagina"),
        ("instagram_last_post_at", "12/11/2026"),
        ("instagram_last_post_at", (date.today() + timedelta(days=10)).isoformat()),
    ],
)
def test_invalid_values_are_rejected(client, field: str, value: str) -> None:
    response = _post(client, name="Bar Prova", **{field: value})
    assert response.status_code == 422


def test_existing_company_keeps_newest_post_date(client) -> None:
    """Aggiornare la data di un'azienda già in CRM passa dall'import per company_id."""
    first = _post(client, name="Pasticceria Dolce", instagram_handle="dolce.tv", instagram_last_post_at="2026-11-05")
    company_id = first.json()["company_id"]

    def update(day: str) -> dict:
        response = client.post("/companies/import", json={"rows": [
            {"ref": day, "company_id": company_id, "instagram_last_post_at": day}]})
        assert response.status_code == 200, response.text
        return response.json()["rows"][0]

    assert "instagram_last_post_at" in update("2026-11-15")["changes"]
    assert client.get(f"/companies/{company_id}").json()["instagram_last_post_at"] == "2026-11-15"
    older = update("2026-11-01")
    assert client.get(f"/companies/{company_id}").json()["instagram_last_post_at"] == "2026-11-15"
    assert any("più vecchia" in warning for warning in older["warnings"])


def test_duplicate_handle_is_rejected_with_existing_id(client) -> None:
    """Accettazione voce 4: stesso instagram_handle (normalizzato) → 409 con l'id esistente."""
    first = _post(client, name="Bar Centrale", instagram_handle="barcentrale.tv").json()

    for body in (
        {"name": "Bar Centrale", "instagram_handle": "@BarCentrale.TV"},
        {"name": "Altro nome", "city": "Venezia", "instagram_handle": "https://www.instagram.com/barcentrale.tv/"},
        {"name": "Solo link", "social_links": [{"label": "Instagram", "url": "instagram.com/BarCentrale.tv"}]},
    ):
        response = client.post("/companies", json=body)
        assert response.status_code == 409, body
        assert response.json()["outcome"] == "duplicate"
        assert response.json()["company_id"] == first["company_id"]
        assert response.json()["candidates"][0]["reasons"] == ["stesso profilo Instagram"]
    assert len(client.get("/opportunities", params={"q": "barcentrale.tv"}).json()) == 1

    # Con allow_duplicates resta la deduplica per social (ADR-022): senza città concordante non fonde.
    forced = client.post("/companies", json={"name": "Bar Centrale", "instagram_handle": "barcentrale.tv",
                                             "allow_duplicates": True})
    assert forced.status_code == 409
    assert forced.json()["outcome"] == "conflict"


def test_import_rows_update_instagram_fields_by_company_id(client) -> None:
    created = _post(client, name="Tappezzeria Rossi").json()
    response = client.post(
        "/companies/import",
        json={"rows": [{"ref": "r1", "company_id": created["company_id"], "instagram_handle": "tappezzeria.rossi",
                        "instagram_last_post_at": "2026-11-18"}]},
    )
    assert response.status_code == 200, response.text
    assert set(response.json()["rows"][0]["changes"]) >= {"instagram_handle", "instagram_last_post_at"}
    company = client.get(f"/companies/{created['company_id']}").json()
    assert company["instagram_handle"] == "tappezzeria.rossi"
    assert company["instagram_last_post_at"] == "2026-11-18"


# --- scheda: PUT /companies/{id}/contacts ---------------------------------------------


def test_contacts_update_sets_keeps_and_clears_instagram_fields(client) -> None:
    created = _post(client, name="Vivaio Verde").json()
    url = f"/companies/{created['company_id']}/contacts"

    saved = client.put(url, json={"phone": "", "email": "", "instagram_handle": "@vivaio.verde",
                                  "instagram_last_post_at": "2026-11-10"})
    assert saved.status_code == 200, saved.text
    assert saved.json()["instagram_handle"] == "vivaio.verde"
    assert saved.json()["instagram_last_post_at"] == "2026-11-10"

    # Campi assenti: invariati.
    kept = client.put(url, json={"phone": "0422 123456", "email": ""}).json()
    assert kept["instagram_handle"] == "vivaio.verde"
    assert kept["instagram_last_post_at"] == "2026-11-10"

    cleared = client.put(url, json={"phone": "0422 123456", "email": "", "instagram_handle": None,
                                    "instagram_last_post_at": None}).json()
    assert cleared["instagram_handle"] is None
    assert cleared["instagram_last_post_at"] is None

    assert client.put(url, json={"phone": "", "email": "", "instagram_handle": "con spazi"}).status_code == 422


# --- GET /opportunities?channel=ig&last_post_after= -----------------------------------


@pytest.fixture
def ig_pipeline(client, db_session) -> None:
    """12 attività senza sito qualificate via IG il 19/11 (date diverse) più aziende senza IG."""
    for index in range(12):
        _post(
            client,
            name=f"Attività IG {index:02d}",
            instagram_handle=f"attivita.ig{index:02d}",
            instagram_last_post_at=(date(2026, 11, 1) + timedelta(days=index)).isoformat(),  # 1→12 novembre
        )
    _post(client, name="IG senza data", instagram_handle="senza.data")
    _post(client, name="Solo telefono", phone="+39 0422 000000")
    # Profilo IG presente solo nei tag OSM (discovery), nessun campo compilato.
    company = Company(name="Pizzeria OSM", source="openstreetmap", status="discovered",
                      extra={"osm_tags": {"amenity": "restaurant", "contact:instagram": "pizzeriaosm"}})
    db_session.add(company)
    db_session.flush()
    db_session.add(Opportunity(company_id=company.id, status="discovered", is_favorite=False))
    db_session.commit()


def _names(response) -> list[str]:
    return sorted(item["company_name"] for item in response.json())


def test_channel_ig_returns_only_instagram_companies(client, ig_pipeline) -> None:
    response = client.get("/opportunities", params={"channel": "ig"})
    assert response.status_code == 200
    names = _names(response)
    assert len(names) == 14
    assert "Solo telefono" not in names
    assert {"IG senza data", "Pizzeria OSM"} <= set(names)
    assert response.headers["x-total-count"] == "14"
    osm = next(item for item in response.json() if item["company_name"] == "Pizzeria OSM")
    assert osm["instagram_handle"] == "pizzeriaosm"


def test_last_post_after_is_inclusive_and_combines_with_channel(client, ig_pipeline) -> None:
    response = client.get("/opportunities", params={"channel": "ig", "last_post_after": "2026-11-10"})
    assert _names(response) == ["Attività IG 09", "Attività IG 10", "Attività IG 11"]  # 10, 11, 12 novembre
    assert response.headers["x-total-count"] == "3"
    assert all(item["instagram_last_post_at"] >= "2026-11-10" for item in response.json())
    only_date = client.get("/opportunities", params={"last_post_after": "2026-11-12"})
    assert _names(only_date) == ["Attività IG 11"]
    paged = client.get("/opportunities", params={"channel": "ig", "last_post_after": "2026-11-01", "limit": 5})
    assert len(paged.json()) == 5 and paged.headers["x-total-count"] == "12"


def test_instagram_filters_validate_input(client) -> None:
    assert client.get("/opportunities", params={"channel": "tiktok"}).status_code == 422
    assert client.get("/opportunities", params={"last_post_after": "19/11/2026"}).status_code == 422


def test_export_honours_instagram_filters(client, ig_pipeline) -> None:
    exported = client.get("/opportunities/export", params={"channel": "ig", "last_post_after": "2026-11-12"}).json()
    assert [item["name"] for item in exported["companies"]] == ["Attività IG 11"]
    assert exported["companies"][0]["instagram_handle"] == "attivita.ig11"
    assert exported["companies"][0]["instagram_last_post_at"] == "2026-11-12"


# --- q: nome, dominio, handle social ---------------------------------------------------


@pytest.fixture
def search_pipeline(db_session) -> None:
    def add(name: str, **fields) -> None:
        domain = fields.pop("domain", None)
        company = Company(name=name, source="test", status="discovered", **fields)
        db_session.add(company)
        db_session.flush()
        if domain:
            db_session.add(Website(company_id=company.id, url=f"http://{domain}/", normalized_url=f"http://{domain}",
                                   domain=domain))
        db_session.add(Opportunity(company_id=company.id, status="discovered", is_favorite=False))

    add("Tappezzeria Mazza di Mazza Andrea & C.", website_url="http://www.2-emme.com/", domain="www.2-emme.com")
    add("Albergo Monte Civetta", extra={"social_links": [
        {"label": "Instagram", "url": "https://www.instagram.com/albergomontecivetta/"}]})
    add("Panificio Pavan", instagram_handle="forno.pavan")
    add("Bar Sport", extra={"social_links": [{"label": "Facebook", "url": "https://facebook.com/barsport.treviso"}]})
    add("Fioraio Rosa", extra={"osm_tags": {"shop": "florist", "opening_hours": "Mo-Sa 09:00-12:30"}})
    db_session.commit()


@pytest.mark.parametrize(
    ("needle", "expected"),
    [
        ("2-emme", ["Tappezzeria Mazza di Mazza Andrea & C."]),  # dominio del sito
        ("2-emme.com", ["Tappezzeria Mazza di Mazza Andrea & C."]),
        ("montecivetta", ["Albergo Monte Civetta"]),  # handle IG dai link social (non nel nome)
        ("@albergomontecivetta", ["Albergo Monte Civetta"]),
        ("forno.pavan", ["Panificio Pavan"]),  # handle IG salvato
        ("barsport.treviso", ["Bar Sport"]),  # handle Facebook
        ("mazza", ["Tappezzeria Mazza di Mazza Andrea & C."]),  # nome, come prima
    ],
)
def test_q_searches_name_domain_and_social_handles(client, search_pipeline, needle: str, expected: list[str]) -> None:
    response = client.get("/opportunities", params={"q": needle})
    assert _names(response) == expected
    assert response.headers["x-total-count"] == str(len(expected))


def test_q_does_not_match_other_osm_tags(client, search_pipeline) -> None:
    # "florist" e gli orari sono nei tag OSM, non in nome/sito/social: niente corrispondenza.
    assert client.get("/opportunities", params={"q": "florist"}).json() == []
    assert client.get("/opportunities", params={"q": "09:00"}).json() == []
    assert _names(client.get("/opportunities", params={"search": "2-emme"})) == [
        "Tappezzeria Mazza di Mazza Andrea & C."
    ]


# --- import in blocco di profili Instagram ---------------------------------------------


def test_instagram_import_creates_only_new_and_reports_duplicates(client) -> None:
    """Accettazione voce 4: 5 righe con 2 duplicati → 3 create, 2 segnalate."""
    existing = _post(client, name="Fiori di Lia", instagram_handle="fiori.lia").json()

    response = client.post("/companies/instagram-import", json={
        "items": [
            "@Fiori.Lia",  # già in CRM
            "https://www.instagram.com/panificio.alforno/",
            "dolce.tv",
            "@Panificio.AlForno",  # ripetuto nella lista
            {"instagram": "vivaio.verde", "name": "Vivaio Verde", "city": "Treviso",
             "instagram_last_post_at": "2026-11-20"},
        ],
        "defaults": {"province": "Treviso", "tags": ["ricerca-ig-20261121"]},
    })

    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["created"], body["duplicates"], body["invalid"]) == (3, 2, 0)
    outcomes = [(row["instagram_handle"], row["outcome"]) for row in body["rows"]]
    assert outcomes == [
        ("fiori.lia", "duplicate"),
        ("panificio.alforno", "created"),
        ("dolce.tv", "created"),
        ("panificio.alforno", "duplicate"),
        ("vivaio.verde", "created"),
    ]
    assert body["rows"][0]["company_id"] == existing["company_id"]
    assert body["rows"][3]["company_id"] == body["rows"][1]["company_id"]
    assert body["rows"][3]["reasons"] == ["ripetuto nella lista"]

    vivaio = client.get(f"/opportunities/{body['rows'][4]['opportunity_id']}").json()
    assert vivaio["company_name"] == "Vivaio Verde"
    assert vivaio["instagram_last_post_at"] == "2026-11-20"
    assert [tag["name"] for tag in vivaio["tags"]] == ["ricerca-ig-20261121"]
    assert client.get("/opportunities", params={"channel": "ig"}).headers["x-total-count"] == "4"


def test_instagram_import_dry_run_and_invalid_rows(client) -> None:
    _post(client, name="Fiori di Lia", instagram_handle="fiori.lia")
    body = client.post("/companies/instagram-import", json={
        "items": ["fiori.lia", "nuovo.profilo", "non valido!", "https://www.instagram.com/p/C0abc/"],
        "dry_run": True,
    }).json()
    assert [row["outcome"] for row in body["rows"]] == ["duplicate", "would_create", "invalid", "invalid"]
    assert body["created"] == 0
    assert client.get("/opportunities", params={"q": "nuovo.profilo"}).json() == []
