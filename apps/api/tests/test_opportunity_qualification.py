"""Filtro multi-tag (intersezione) e campi espliciti canale proposto / difetto visto."""

from __future__ import annotations

import pytest

LOTTO = "lotto4-riserva-20261121"
IG = "canale-ig-proposto"


def _create(client, name: str, **body) -> dict:
    response = client.post("/companies", json={"name": name, "city": "Bergamo", **body})
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def tagged(client) -> dict[str, dict]:
    return {
        "both": _create(client, "CEnERE Forno", tags=[LOTTO, IG, "concept-da-fare"]),
        "lotto_only": _create(client, "Fioraio Bergamo", tags=[LOTTO]),
        "ig_only": _create(client, "Barbiere Alto", tags=[IG]),
        "none": _create(client, "Bar Senza Tag"),
    }


def _names(response) -> list[str]:
    return sorted(item["company_name"] for item in response.json())


def test_repeated_tag_filter_returns_the_intersection(client, tagged) -> None:
    """Accettazione: ?tag=lotto4-riserva-20261121&tag=canale-ig-proposto = solo chi ha entrambi."""
    response = client.get("/opportunities", params=[("tag", LOTTO), ("tag", IG)])
    assert _names(response) == ["CEnERE Forno"]
    assert response.headers["x-total-count"] == "1"

    assert _names(client.get("/opportunities", params={"tag": LOTTO})) == ["CEnERE Forno", "Fioraio Bergamo"]
    upper = client.get("/opportunities", params=[("tag", LOTTO.upper()), ("tag", IG), ("tag", IG)])
    assert _names(upper) == ["CEnERE Forno"]
    none = client.get("/opportunities", params=[("tag", LOTTO), ("tag", "tag-inesistente")])
    assert none.json() == [] and none.headers["x-total-count"] == "0"


def test_multi_tag_filter_also_applies_to_export_and_pages(client, tagged) -> None:
    exported = client.get("/opportunities/export", params=[("tag", LOTTO), ("tag", IG)]).json()
    assert [item["name"] for item in exported["companies"]] == ["CEnERE Forno"]
    page = client.get("/opportunities", params=[("tag", LOTTO), ("limit", "1"), ("offset", "1")])
    assert len(page.json()) == 1 and page.headers["x-total-count"] == "2"


def test_post_companies_accepts_proposed_channel_and_observed_issue(client) -> None:
    created = _create(client, "Tappezzeria Prandelli", proposed_channel="IG",
                      observed_issue="Galleria lavori solo su Instagram, sito senza contatti da mobile",
                      tags=[LOTTO])
    detail = client.get(f"/opportunities/{created['opportunity_id']}").json()
    assert detail["proposed_channel"] == "instagram"
    assert detail["observed_issue"] == "Galleria lavori solo su Instagram, sito senza contatti da mobile"
    assert [tag["name"] for tag in detail["tags"]] == [LOTTO]

    bad = client.post("/companies", json={"name": "Altra", "proposed_channel": "piccione viaggiatore"})
    assert bad.status_code == 422


def test_fields_are_editable_in_the_opportunity_card(client) -> None:
    created = _create(client, "Panificio Treviglio")
    url = f"/opportunities/{created['opportunity_id']}"

    saved = client.patch(url, json={"proposed_channel": "email", "observed_issue": "  Orari non aggiornati  "})
    assert saved.status_code == 200
    assert (saved.json()["proposed_channel"], saved.json()["observed_issue"]) == ("email", "Orari non aggiornati")

    kept = client.patch(url, json={"is_favorite": True}).json()  # campi assenti: invariati
    assert (kept["proposed_channel"], kept["observed_issue"]) == ("email", "Orari non aggiornati")

    cleared = client.patch(url, json={"proposed_channel": None, "observed_issue": ""}).json()
    assert (cleared["proposed_channel"], cleared["observed_issue"]) == (None, None)

    assert client.patch(url, json={"proposed_channel": "fax"}).status_code == 422


def test_filter_by_proposed_channel(client) -> None:
    _create(client, "A", proposed_channel="instagram")
    _create(client, "B", proposed_channel="email")
    _create(client, "C")
    assert _names(client.get("/opportunities", params={"proposed_channel": "ig"})) == ["A"]
    assert _names(client.get("/opportunities", params={"proposed_channel": "email"})) == ["B"]
    assert client.get("/opportunities", params={"proposed_channel": "fax"}).status_code == 422


def test_import_fills_empty_fields_without_overwriting(client) -> None:
    created = _create(client, "Vivaio Verde", proposed_channel="email")
    response = client.post("/companies/import", json={"rows": [{
        "ref": "r1", "company_id": created["company_id"], "proposed_channel": "instagram",
        "observed_issue": "Nessun prezzo online",
    }]})
    row = response.json()["rows"][0]
    assert "observed_issue" in row["changes"]
    assert any("proposed_channel" in warning for warning in row["warnings"])
    detail = client.get(f"/opportunities/{created['opportunity_id']}").json()
    assert (detail["proposed_channel"], detail["observed_issue"]) == ("email", "Nessun prezzo online")
