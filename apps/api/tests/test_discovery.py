from app.config import Settings
from app.discovery.normalize import normalize_candidate, normalize_phone
from app.discovery.italy_geo import compose_location
from app.discovery.osm import (
    OpenStreetMapProvider,
    _build_overpass_query,
    _category_from_tags,
    _from_nominatim,
    _from_osm,
    candidate_matches_industry,
    element_coords,
    empty_search_message,
    format_industry_tags,
    industry_name_regex,
    industry_tags,
    overpass_error_message,
    parse_osm_external_id,
    preview_industry,
    resolve_search_tags,
    select_candidates,
)
from app.discovery.service import (
    _run_discovery,
    create_discovery_run,
    get_company,
    list_companies,
    load_discovery_run,
)
from app.discovery.types import DiscoveryCandidate, DiscoveryQuery
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
    assert industry_tags("barbiere") == [("shop", "hairdresser"), ("craft", "hairdresser")]
    assert industry_tags("parrucchieri") == [("shop", "hairdresser")]
    assert industry_tags("dentista") == [("amenity", "dentist")]
    assert industry_tags("meccanico") == [("shop", "car_repair")]
    assert industry_tags("shop=car_repair") == [("shop", "car_repair")]
    assert industry_tags("car_repair") == [("shop", "car_repair")]
    assert industry_tags("settore inesistente xyz") == []
    assert industry_name_regex("barbiere") is None
    assert industry_name_regex("studio grafico") == r"studio\ grafico"


def test_unknown_industry_does_not_search_hotels() -> None:
    query = _build_overpass_query(
        {"bbox": ["40.0", "41.0", "15.0", "16.0"]},
        industry_tags("barbiere"),
        20,
        15,
    )
    assert '["shop"="hairdresser"]' in query
    assert '["tourism"="hotel"]' not in query
    assert industry_tags("studio grafico") == []
    preview = preview_industry("studio grafico")
    assert preview["mapped"] is False
    assert preview["tags"] == []
    message = empty_search_message("studio grafico", "Manfredonia")
    assert "non corrisponde a un tag OpenStreetMap noto" in message
    assert "altri settori" in message


def test_category_uses_osm_tag_when_search_mismatches() -> None:
    assert _category_from_tags({"shop": "hairdresser"}, "barbiere") == "barbiere"
    assert _category_from_tags({"tourism": "hotel"}, "barbiere") == "hotel"
    hairdresser = _from_osm(
        {
            "type": "node",
            "id": 1,
            "lat": 41.6,
            "lon": 15.9,
            "tags": {"name": "Da Mario", "shop": "hairdresser"},
        },
        "barbiere",
    )
    hotel = _from_osm(
        {
            "type": "node",
            "id": 2,
            "lat": 41.6,
            "lon": 15.9,
            "tags": {"name": "Hotel Sole", "tourism": "hotel"},
        },
        "barbiere",
    )
    assert hairdresser is not None and candidate_matches_industry(hairdresser, "barbiere")
    assert hotel is not None and not candidate_matches_industry(hotel, "barbiere")
    assert format_industry_tags("barbiere") == ["shop=hairdresser", "craft=hairdresser"]


def test_osm_keeps_start_date_and_opening_hours() -> None:
    candidate = _from_osm(
        {
            "type": "node",
            "id": 3,
            "lat": 41.6,
            "lon": 15.9,
            "tags": {
                "name": "Officina Rossi",
                "shop": "car_repair",
                "start_date": "1998",
                "opening_hours": "Mo-Fr 08:00-18:00",
            },
        },
        "meccanico",
    )
    assert candidate is not None
    assert candidate.extra is not None
    assert candidate.extra["osm_tags"]["shop"] == "car_repair"
    assert candidate.extra["osm_tags"]["start_date"] == "1998"
    assert candidate.extra["osm_tags"]["opening_hours"] == "Mo-Fr 08:00-18:00"


def test_osm_falls_back_to_mobile_and_keeps_social_tags() -> None:
    candidate = _from_osm(
        {
            "type": "node",
            "id": 4,
            "lat": 41.9,
            "lon": 12.5,
            "tags": {
                "name": "Trattoria da Elvira",
                "amenity": "restaurant",
                "contact:mobile": "+39 333 1234567",
                "contact:instagram": "trattoriaelvira",
            },
        },
        "ristorante",
    )
    assert candidate is not None
    assert candidate.phone == "+39 333 1234567"
    assert candidate.email is None
    assert candidate.extra["osm_tags"]["contact:instagram"] == "trattoriaelvira"


def test_social_contact_link_prefers_whatsapp_then_facebook_then_instagram() -> None:
    from app.discovery.osm import social_contact_link

    assert social_contact_link(None) is None
    assert social_contact_link({}) is None
    assert social_contact_link({"contact:whatsapp": "+39 333 1234567"}) == ("WhatsApp", "https://wa.me/393331234567")
    assert social_contact_link({"contact:facebook": "trattoriaelvira"}) == (
        "Facebook",
        "https://facebook.com/trattoriaelvira",
    )
    assert social_contact_link({"facebook": "https://facebook.com/pagina"}) == (
        "Facebook",
        "https://facebook.com/pagina",
    )
    assert social_contact_link({"instagram": "@trattoriaelvira"}) == (
        "Instagram",
        "https://instagram.com/trattoriaelvira",
    )
    assert social_contact_link(
        {"contact:whatsapp": "+39 333 1234567", "contact:facebook": "x"}
    ) == ("WhatsApp", "https://wa.me/393331234567")


def test_osm_element_coords_from_node_and_center() -> None:
    assert element_coords({"lat": 38.1, "lon": 13.3}) == (38.1, 13.3)
    assert element_coords({"center": {"lat": 37.5, "lon": 15.1}}) == (37.5, 15.1)
    assert element_coords({"tags": {"name": "x"}}) is None
    candidate = _from_osm(
        {
            "type": "way",
            "id": 99,
            "center": {"lat": 38.1157, "lon": 13.3615},
            "tags": {"name": "Hotel Sole", "addr:city": "Palermo"},
        },
        "Hotel",
    )
    assert candidate is not None
    assert candidate.latitude == 38.1157
    assert candidate.longitude == 13.3615
    assert candidate.city == "Palermo"


def test_parse_osm_external_id_and_overpass_error_hides_html() -> None:
    assert parse_osm_external_id("node/123") == ("node", 123)
    assert parse_osm_external_id("way/99") == ("way", 99)
    assert parse_osm_external_id("n/1") is None
    message = overpass_error_message(504, '<?xml version="1.0"?><html>Gateway Timeout</html>')
    assert "<?xml" not in message
    assert "html" not in message.lower()
    assert "timeout" in message.lower() or "sovraccarico" in message.lower()


def test_from_nominatim_keeps_coords() -> None:
    candidate = _from_nominatim(
        {
            "name": "Hotel Sole",
            "lat": "38.1157",
            "lon": "13.3615",
            "osm_type": "way",
            "osm_id": 99,
            "address": {"city": "Palermo"},
            "extratags": {"website": "https://hotelsole.it"},
        },
        "Hotel",
    )
    assert candidate is not None
    assert candidate.latitude == 38.1157
    assert candidate.longitude == 13.3615
    assert candidate.external_id == "way/99"
    assert candidate.website_url == "https://hotelsole.it"


def test_search_does_not_substitute_other_sectors_when_overpass_fails(monkeypatch) -> None:
    import pytest

    provider = OpenStreetMapProvider(Settings())
    monkeypatch.setattr(provider, "_resolve_area", lambda _loc: {"bbox": ["36", "38", "12", "15"]})

    def fail_overpass(*_args, **_kwargs):
        raise RuntimeError(overpass_error_message(504, "<?xml version='1.0'?>"))

    monkeypatch.setattr(provider, "_overpass", fail_overpass)
    monkeypatch.setattr(
        provider,
        "_nominatim_search",
        lambda _query, _area: [
            DiscoveryCandidate(
                name="Hotel Test",
                city="Palermo",
                latitude=38.1,
                longitude=13.3,
                source="openstreetmap",
                extra={"osm_tags": {"tourism": "hotel"}},
                external_id="node/1",
            )
        ],
    )
    with pytest.raises(RuntimeError, match="timeout|sovraccarico"):
        provider.search_businesses(DiscoveryQuery(industry="barbiere", location="Manfredonia", max_results=20))


def test_select_candidates_standard_prefers_website() -> None:
    with_site = DiscoveryCandidate(name="Con sito", website_url="https://a.it", source="t", external_id="1")
    without = DiscoveryCandidate(name="Senza sito", source="t", external_id="2")
    standard = DiscoveryQuery(industry="Hotel", location="Palermo", max_results=20)
    picked = select_candidates([without, with_site], standard)
    assert [item.name for item in picked] == ["Con sito"]
    extended = DiscoveryQuery(
        industry="Hotel", location="Palermo", max_results=20, include_without_website=True
    )
    both = select_candidates([without, with_site], extended)
    assert {item.name for item in both} == {"Con sito", "Senza sito"}


def test_create_discovery_extended_allows_over_50(client, monkeypatch) -> None:
    monkeypatch.setattr("app.api.discovery.execute_discovery", lambda run_id: None)
    denied = client.post(
        "/discoveries",
        json={"industry": "Hotel", "location": "Palermo", "max_results": 100},
    )
    assert denied.status_code == 422
    created = client.post(
        "/discoveries",
        json={"industry": "Hotel", "location": "Palermo", "max_results": 100, "extended": True},
    )
    assert created.status_code == 202
    assert created.json()["extended"] is True
    assert created.json()["max_results"] == 100


def test_osm_preview_endpoint(client) -> None:
    mapped = client.get("/discovery/osm-preview", params={"industry": "barbiere"})
    assert mapped.status_code == 200
    body = mapped.json()
    assert body["mapped"] is True
    assert "shop=hairdresser" in body["tags"]
    assert "meccanico" in body["sectors"]
    unknown = client.get("/discovery/osm-preview", params={"industry": "studio grafico"})
    assert unknown.status_code == 200
    assert unknown.json()["mapped"] is False
    assert unknown.json()["tags"] == []
    universal = client.get("/discovery/osm-preview")
    assert universal.status_code == 200
    assert universal.json()["mapped"] is True
    assert "shop" in universal.json()["tags"]


def test_discovery_catalog_cascades_geo(client) -> None:
    assert compose_location() == "Italia"
    assert compose_location(region="Puglia", province="Foggia", city="Manfredonia") == "Manfredonia, Foggia, Puglia"
    response = client.get("/discovery/catalog")
    assert response.status_code == 200
    body = response.json()
    assert "meccanico" in body["sectors"]
    puglia = next(item for item in body["regions"] if item["name"] == "Puglia")
    foggia = next(item for item in puglia["provinces"] if item["name"] == "Foggia")
    assert "Manfredonia" in foggia["cities"]


def test_create_discovery_allows_empty_filters(client, monkeypatch) -> None:
    monkeypatch.setattr("app.api.discovery.execute_discovery", lambda run_id: None)
    created = client.post("/discoveries", json={"max_results": 10})
    assert created.status_code == 202
    assert created.json()["industry"] == "tutti"
    assert created.json()["location"] == "Italia"
    cascaded = client.post(
        "/discoveries",
        json={
            "industry": "meccanico",
            "region": "Puglia",
            "province": "Foggia",
            "city": "Manfredonia",
            "max_results": 10,
        },
    )
    assert cascaded.status_code == 202
    assert cascaded.json()["location"] == "Manfredonia, Foggia, Puglia"


def test_universal_overpass_matches_any_commercial_key() -> None:
    query = _build_overpass_query(
        {"bbox": ["40.0", "41.0", "15.0", "16.0"]},
        resolve_search_tags(""),
        20,
        15,
    )
    assert 'node["shop"](' in query
    assert '["shop"="*"]' not in query


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
                    latitude=38.1157,
                    longitude=13.3615,
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
    assert run.progress_percent == 100
    assert run.progress_label == "Completata"
    companies = list_companies(db_session)
    assert len(companies) == 2
    names = sorted(item.name for item in companies)
    assert names == ["Hotel Luna", "Hotel Sole"]
    sole = next(item for item in companies if item.name == "Hotel Sole")
    assert sole.websites[0].domain == "hotelsole.it"
    loaded_company = get_company(db_session, sole.id)
    assert loaded_company is not None
    assert loaded_company.latitude == 38.1157
    assert loaded_company.longitude == 13.3615

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
    assert payload["progress_percent"] == 0
    assert payload["progress_label"] == "In coda"
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


def test_company_summary_exposes_social_fallback(client, db_session) -> None:
    company = Company(
        name="Trattoria Senza Sito",
        category="Ristorante",
        city="Palermo",
        source="fake",
        external_id="x/2",
        status="discovered",
        phone=None,
        email=None,
        latitude=38.1157,
        longitude=13.3615,
        extra={"osm_tags": {"contact:instagram": "trattoriasenzasito"}},
    )
    db_session.add(company)
    db_session.commit()
    response = client.get(f"/companies/{company.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["phone"] is None
    assert body["social_label"] == "Instagram"
    assert body["social_url"] == "https://instagram.com/trattoriasenzasito"
    assert body["latitude"] == 38.1157
    assert body["longitude"] == 13.3615
