from app.config import Settings
from app.discovery.normalize import normalize_candidate, normalize_phone
from app.discovery.osm import industry_tags
from app.discovery.service import (
    _run_discovery,
    create_discovery_run,
    get_company,
    list_companies,
    load_discovery_run,
)
from app.discovery.types import DiscoveryCandidate
from app.models.entities import Company


def test_normalize_phone_and_skip_nameless() -> None:
    assert normalize_phone("+39 091 123 456") == "+39091123456"
    assert (
        normalize_candidate(
            DiscoveryCandidate(name="  ", website_url="https://x.it", source="t", external_id="1")
        )
        is None
    )


def test_normalize_drops_invalid_website() -> None:
    result = normalize_candidate(
        DiscoveryCandidate(name="Hotel A", website_url="ftp://nope", source="t", external_id="1")
    )
    assert result is not None
    assert result.website_url is None


def test_industry_tags_map_hotel_and_restaurant() -> None:
    assert industry_tags("Hotel") == [("tourism", "hotel")]
    assert industry_tags("Ristoranti") == [("amenity", "restaurant")]


def test_discovery_persists_dedupes_and_links_website(db_session, monkeypatch) -> None:
    class Fake:
        name = "fake"

        def search_businesses(self, query):
            assert query.location == "Sicilia"
            return [
                DiscoveryCandidate(
                    name="Hotel Sole",
                    city="Palermo",
                    website_url="https://HotelSole.it/home/",
                    phone="091111",
                    source="fake",
                    external_id="n/1",
                ),
                DiscoveryCandidate(
                    name="Hotel Sole",
                    city="Palermo",
                    website_url="https://hotelsole.it",
                    source="fake",
                    external_id="n/1",
                ),
                DiscoveryCandidate(
                    name="Hotel Luna",
                    city="Catania",
                    website_url="https://hotelluna.it",
                    source="fake",
                    external_id="n/2",
                ),
            ]

    monkeypatch.setattr("app.discovery.service.get_discovery_provider", lambda settings: Fake())
    run = create_discovery_run(db_session, industry="Hotel", location="Sicilia", max_results=20)
    _run_discovery(db_session, run, Settings())
    db_session.commit()

    assert run.status == "completed"
    assert run.total_found == 2
    companies = list_companies(db_session)
    assert len(companies) == 2
    names = sorted(item.name for item in companies)
    assert names == ["Hotel Luna", "Hotel Sole"]
    sole = next(item for item in companies if item.name == "Hotel Sole")
    assert sole.websites[0].domain == "hotelsole.it"

    loaded = load_discovery_run(db_session, run.id)
    assert loaded is not None
    assert len(loaded.results) == 2
    assert get_company(db_session, sole.id) is not None


def test_create_discovery_api_queues_job(client, monkeypatch) -> None:
    monkeypatch.setattr("app.api.discovery.execute_discovery", lambda run_id: None)
    created = client.post(
        "/discoveries",
        json={"industry": "Hotel", "location": "Sicilia", "max_results": 5},
    )
    assert created.status_code == 202
    payload = created.json()
    assert payload["status"] == "queued"
    assert payload["industry"] == "Hotel"
    fetched = client.get(f"/discoveries/{payload['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["companies"] == []


def test_list_recent_discoveries(client, monkeypatch) -> None:
    monkeypatch.setattr("app.api.discovery.execute_discovery", lambda run_id: None)
    client.post("/discoveries", json={"industry": "Hotel", "location": "Palermo", "max_results": 5})
    client.post("/discoveries", json={"industry": "Ristorante", "location": "Catania", "max_results": 5})
    listed = client.get("/discoveries")
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) >= 2
    assert {item["industry"] for item in rows} >= {"Hotel", "Ristorante"}


def test_companies_empty_and_missing(client) -> None:
    assert client.get("/companies").json() == []
    response = client.get("/companies/11111111-1111-1111-1111-111111111111")
    assert response.status_code == 404


def test_company_detail_after_persist(client, db_session) -> None:
    company = Company(
        name="Hotel Test",
        category="Hotel",
        city="Palermo",
        source="fake",
        external_id="x/1",
        status="discovered",
        website_url="https://hoteltest.it",
    )
    db_session.add(company)
    db_session.commit()
    response = client.get(f"/companies/{company.id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Hotel Test"
