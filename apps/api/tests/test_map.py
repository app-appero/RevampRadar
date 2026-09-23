from datetime import UTC, datetime

from app.models.entities import Audit, Company, OpportunityScore, Website, WebsiteScore


def test_map_empty(client) -> None:
    response = client.get("/map")
    assert response.status_code == 200
    payload = response.json()
    assert payload["points"] == []
    assert payload["clusters"] == []
    assert payload["mapped_count"] == 0
    assert payload["unmapped_count"] == 0


def test_map_clusters_scored_points(client, db_session) -> None:
    palermo = _company(db_session, "Hotel Sole", "Palermo", 38.1157, 13.3615)
    milan = _company(db_session, "Hotel Duomo", "Milano", 45.4642, 9.1900)
    _company(db_session, "Baia", "Panarea", 38.638, 15.078, website=False)
    _company(db_session, "Senza pin", "Catania", None, None)
    _completed_audit(
        db_session,
        palermo,
        opportunity_score=82,
        priority="HIGH",
        html={"app_links": [{"store": "app_store", "url": "https://apps.apple.com/app/id1"}]},
    )
    _completed_audit(db_session, milan, opportunity_score=41, priority="LOW", html={})
    db_session.commit()

    response = client.get("/map")
    assert response.status_code == 200
    payload = response.json()
    assert payload["mapped_count"] == 3
    assert payload["unmapped_count"] == 1
    names = {item["name"] for item in payload["points"]}
    assert names == {"Hotel Sole", "Hotel Duomo", "Baia"}
    sole = next(item for item in payload["points"] if item["name"] == "Hotel Sole")
    assert sole["opportunity_score"] == 82
    assert sole["priority"] == "HIGH"
    assert sole["has_app"] is True
    assert sole["has_website"] is True
    assert sole["city"] == "Palermo"
    duomo = next(item for item in payload["points"] if item["name"] == "Hotel Duomo")
    assert duomo["has_app"] is False
    baia = next(item for item in payload["points"] if item["name"] == "Baia")
    assert baia["has_website"] is False
    assert baia["has_app"] is False
    assert baia["opportunity_score"] is None
    assert baia["is_contactable"] is False
    assert sole["is_contactable"] is True
    assert len(payload["clusters"]) >= 1
    assert all("P(accett" not in cluster["label"] for cluster in payload["clusters"])
    baia_cluster = next(item for item in payload["clusters"] if item["id"] == baia["cluster_id"])
    assert baia_cluster["no_site_share"] > 0
    assert "senza sito" in baia_cluster["label"]


def test_map_contactable_via_social_even_without_website(client, db_session) -> None:
    company = _company(db_session, "Trattoria Social", "Palermo", 38.1157, 13.3615, website=False)
    company.extra = {"osm_tags": {"contact:whatsapp": "+39 333 1234567"}}
    db_session.commit()

    response = client.get("/map")
    assert response.status_code == 200
    point = next(item for item in response.json()["points"] if item["name"] == "Trattoria Social")
    assert point["has_website"] is False
    assert point["is_contactable"] is True


def test_map_backfill_sets_coords_from_osm_id(client, db_session, monkeypatch) -> None:
    company = _company(db_session, "Hotel Mare", "Palermo", None, None)
    company.source = "openstreetmap"
    company.external_id = "node/4242"
    db_session.commit()

    monkeypatch.setattr(
        "app.services.map_service.fetch_coords_for_external_ids",
        lambda _settings, ids: {"node/4242": (38.1157, 13.3615)} if "node/4242" in ids else {},
    )
    response = client.post("/map/backfill")
    assert response.status_code == 200
    body = response.json()
    assert body["updated"] == 1
    assert body["remaining"] == 0
    db_session.refresh(company)
    assert company.latitude == 38.1157
    assert company.longitude == 13.3615
    mapped = client.get("/map").json()
    assert mapped["mapped_count"] == 1
    assert mapped["points"][0]["name"] == "Hotel Mare"


def _company(
    session, name: str, city: str, lat: float | None, lon: float | None, *, website: bool = True
) -> Company:
    slug = name.lower().replace(" ", "")
    company = Company(
        name=name,
        city=city,
        category="Hotel",
        source="test",
        external_id=name.lower().replace(" ", "-"),
        latitude=lat,
        longitude=lon,
        website_url=f"https://{slug}.test" if website else None,
    )
    session.add(company)
    session.flush()
    if website:
        site = Website(
            company_id=company.id,
            url=company.website_url,
            normalized_url=company.website_url,
            domain=f"{slug}.test",
        )
        session.add(site)
        session.flush()
    return company


def _completed_audit(session, company: Company, *, opportunity_score: int, priority: str, html: dict) -> Audit:
    website = company.websites[0]
    audit = Audit(
        website_id=website.id,
        status="completed",
        request_url=website.url,
        scanner_version="test",
        completed_at=datetime.now(UTC),
        html_data=html,
    )
    session.add(audit)
    session.flush()
    session.add(
        WebsiteScore(
            audit_id=audit.id,
            technical_score=40,
            performance_score=40,
            ui_score=None,
            ux_score=40,
            mobile_score=40,
            conversion_score=40,
            seo_score=40,
            trust_score=40,
            overall_score=40,
            explanation="t",
            formula_version="1.0.0",
        )
    )
    session.add(
        OpportunityScore(
            audit_id=audit.id,
            company_id=company.id,
            website_score=40,
            business_score=50,
            opportunity_score=opportunity_score,
            confidence=0.5,
            priority=priority,
            explanation="t",
            top_reasons=[],
            positive_factors=[],
            negative_factors=[],
            recommended_service="test",
            formula_version="1.0.0",
        )
    )
    return audit
