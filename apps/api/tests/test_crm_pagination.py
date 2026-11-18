"""Pipeline: paginazione oltre 500 record, filtri tag/nome con totale, GET note, DELETE di un tag."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models.entities import Company, Opportunity, OpportunityNote, OpportunityTag, Tag

TOTAL = 1203
TAGGED = 650
LOTTO3 = "lotto3-20261123"
SAME_MOMENT = datetime(2026, 11, 16, 9, 42, 2, tzinfo=UTC)


@pytest.fixture
def big_pipeline(db_session) -> dict:
    """1203 opportunità con lo stesso updated_at (come un import in blocco), 650 col tag lotto3."""
    lotto3 = Tag(name=LOTTO3)
    other = Tag(name="altro-tag")
    db_session.add_all([lotto3, other])
    db_session.flush()
    companies = [
        Company(
            name=("Ottica " if index % 100 == 0 else "Azienda ") + f"{index:04d}",
            source="test",
            status="discovered",
        )
        for index in range(TOTAL)
    ]
    db_session.add_all(companies)
    db_session.flush()
    opportunities = [
        Opportunity(company_id=company.id, status="discovered", is_favorite=False, updated_at=SAME_MOMENT)
        for company in companies
    ]
    db_session.add_all(opportunities)
    db_session.flush()
    db_session.add_all(
        OpportunityTag(opportunity_id=item.id, tag_id=lotto3.id) for item in opportunities[:TAGGED]
    )
    db_session.add(OpportunityTag(opportunity_id=opportunities[0].id, tag_id=other.id))
    db_session.commit()
    return {"ids": {str(item.id) for item in opportunities}, "first": opportunities[0]}


def _pages(client, params: dict, size: int) -> tuple[list[dict], list[int], set[str]]:
    rows: list[dict] = []
    sizes: list[int] = []
    totals: set[str] = set()
    offset = 0
    while True:
        response = client.get("/opportunities", params={**params, "limit": size, "offset": offset})
        assert response.status_code == 200
        totals.add(response.headers["x-total-count"])
        page = response.json()
        sizes.append(len(page))
        rows.extend(page)
        if len(page) < size:
            return rows, sizes, totals
        offset += size


def test_offset_pages_through_more_than_500_records(client, big_pipeline) -> None:
    rows, sizes, totals = _pages(client, {}, 500)

    assert sizes == [500, 500, 203]
    assert totals == {str(TOTAL)}
    ids = [row["id"] for row in rows]
    assert len(ids) == len(set(ids)) == TOTAL  # nessun record ripetuto o saltato
    assert set(ids) == big_pipeline["ids"]
    # Le pagine concatenate sono esattamente l'elenco completo, nello stesso ordine.
    everything = client.get("/opportunities").json()
    assert [row["id"] for row in everything] == ids
    # Pagine diverse, non "sempre gli stessi record".
    first = client.get("/opportunities", params={"limit": 500, "offset": 0}).json()
    second = client.get("/opportunities", params={"limit": 500, "offset": 500}).json()
    assert not {row["id"] for row in first} & {row["id"] for row in second}


def test_offset_past_the_end_is_empty_with_total(client, big_pipeline) -> None:
    response = client.get("/opportunities", params={"limit": 500, "offset": TOTAL})
    assert response.json() == []
    assert response.headers["x-total-count"] == str(TOTAL)


def test_tag_filter_counts_and_pages(client, big_pipeline) -> None:
    rows, sizes, totals = _pages(client, {"tag": LOTTO3}, 500)

    assert totals == {str(TAGGED)}
    assert sizes == [500, 150]
    assert len({row["id"] for row in rows}) == TAGGED
    assert all(LOTTO3 in {tag["name"] for tag in row["tags"]} for row in rows)
    upper = client.get("/opportunities", params={"tag": LOTTO3.upper(), "limit": 1})
    assert upper.headers["x-total-count"] == str(TAGGED)
    missing = client.get("/opportunities", params={"tag": "lotto9-inesistente", "limit": 10})
    assert missing.json() == [] and missing.headers["x-total-count"] == "0"


def test_name_filter_counts_and_pages(client, big_pipeline) -> None:
    rows, sizes, totals = _pages(client, {"q": "ottica"}, 5)
    assert totals == {"13"}  # indici 0, 100, …, 1200
    assert sizes == [5, 5, 3]
    assert all(row["company_name"].startswith("Ottica") for row in rows)
    assert client.get("/opportunities", params={"search": "ottica", "limit": 1}).headers["x-total-count"] == "13"


def test_pagination_bounds_are_validated(client) -> None:
    assert client.get("/opportunities", params={"limit": 1001}).status_code == 422
    assert client.get("/opportunities", params={"limit": 0}).status_code == 422
    assert client.get("/opportunities", params={"offset": -1}).status_code == 422


# --- GET note --------------------------------------------------------------------------


def _single(db_session) -> Opportunity:
    company = Company(name="Albergo Monte Civetta", source="test", status="discovered")
    db_session.add(company)
    db_session.flush()
    opportunity = Opportunity(company_id=company.id, status="contacted", is_favorite=False)
    db_session.add(opportunity)
    db_session.flush()
    return opportunity


def test_get_notes_lists_notes_newest_first(client, db_session) -> None:
    opportunity = _single(db_session)
    base = datetime(2026, 11, 16, 9, 0, tzinfo=UTC)
    db_session.add(OpportunityNote(opportunity_id=opportunity.id, body="Prima nota", created_at=base))
    db_session.add(
        OpportunityNote(opportunity_id=opportunity.id, body="Seconda nota", created_at=base + timedelta(hours=1))
    )
    db_session.commit()

    response = client.get(f"/opportunities/{opportunity.id}/notes")
    assert response.status_code == 200
    assert [item["body"] for item in response.json()] == ["Seconda nota", "Prima nota"]

    posted = client.post(f"/opportunities/{opportunity.id}/notes", json={"body": "Terza nota"})
    assert posted.status_code == 200
    listed = client.get(f"/opportunities/{opportunity.id}/notes").json()
    assert {item["body"] for item in listed} == {"Prima nota", "Seconda nota", "Terza nota"}
    detail = client.get(f"/opportunities/{opportunity.id}").json()
    assert {item["id"] for item in detail["notes"]} == {item["id"] for item in listed}


def test_get_notes_unknown_opportunity_is_404(client) -> None:
    response = client.get("/opportunities/11111111-1111-1111-1111-111111111111/notes")
    assert response.status_code == 404


# --- DELETE di un tag ------------------------------------------------------------------


def _tagged(client, db_session) -> tuple[str, str]:
    opportunity = _single(db_session)
    other = _single(db_session)
    db_session.commit()
    for name in (LOTTO3, "no-reinvio-automatico"):
        assert client.post(f"/opportunities/{opportunity.id}/tags", json={"name": name}).status_code == 200
    client.post(f"/opportunities/{other.id}/tags", json={"name": LOTTO3})
    return str(opportunity.id), str(other.id)


def test_delete_single_tag_by_name(client, db_session) -> None:
    opportunity_id, other_id = _tagged(client, db_session)

    response = client.delete(f"/opportunities/{opportunity_id}/tags/{LOTTO3}")
    assert response.status_code == 200
    assert [tag["name"] for tag in response.json()["tags"]] == ["no-reinvio-automatico"]
    # Le altre aziende con lo stesso tag non cambiano.
    other = client.get(f"/opportunities/{other_id}").json()
    assert [tag["name"] for tag in other["tags"]] == [LOTTO3]
    assert client.get("/opportunities", params={"tag": LOTTO3, "limit": 10}).headers["x-total-count"] == "1"


def test_delete_single_tag_by_id(client, db_session) -> None:
    opportunity_id, _ = _tagged(client, db_session)
    tags = client.get(f"/opportunities/{opportunity_id}").json()["tags"]
    target = next(tag for tag in tags if tag["name"] == "no-reinvio-automatico")

    response = client.delete(f"/opportunities/{opportunity_id}/tags/{target['id']}")
    assert response.status_code == 200
    assert [tag["name"] for tag in response.json()["tags"]] == [LOTTO3]


def test_delete_tag_not_present_is_404(client, db_session) -> None:
    opportunity_id, _ = _tagged(client, db_session)
    assert client.delete(f"/opportunities/{opportunity_id}/tags/mai-esistito").status_code == 404
    assert client.delete(f"/opportunities/11111111-1111-1111-1111-111111111111/tags/{LOTTO3}").status_code == 404


def test_openapi_documents_pagination_notes_and_tag_delete(client) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    params = {item["name"] for item in paths["/opportunities"]["get"]["parameters"]}
    assert {"limit", "offset", "tag", "q", "search"} <= params
    assert "X-Total-Count" in paths["/opportunities"]["get"]["description"]
    assert "get" in paths["/opportunities/{opportunity_id}/notes"]
    delete = paths["/opportunities/{opportunity_id}/tags/{tag}"]["delete"]
    assert "nome" in delete["description"] and "404" in delete["responses"]
