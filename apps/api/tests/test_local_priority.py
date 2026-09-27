from app.geo import haversine_km
from app.models.entities import Company
from app.proposals.builder import build_proposal_draft
from app.proposals.sender import DEFAULT_SENDER, SenderProfileView


def test_haversine_km_one_degree_at_equator_is_about_111_km() -> None:
    distance = haversine_km(0, 0, 0, 1)
    assert 110 < distance < 112


def test_haversine_km_same_point_is_zero() -> None:
    assert haversine_km(41.46, 15.55, 41.46, 15.55) == 0


def test_settings_geocodes_reference_location_on_change(client, monkeypatch) -> None:
    monkeypatch.setattr("app.services.sender_profile.geocode_point", lambda settings, location: (41.46, 15.55))
    payload = {
        "display_name": "Mario Rossi",
        "intro": "Ciao",
        "website_url": "https://example.test",
        "freelancer_links": [],
        "social_links": [],
        "other_links": [],
        "reference_location": "Foggia, Italia",
        "local_radius_km": 50,
        "local_mention_enabled": True,
        "local_mention_text": "Possiamo vederci di persona.",
    }
    response = client.put("/settings/profile", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["reference_latitude"] == 41.46
    assert body["reference_longitude"] == 15.55


def test_settings_save_survives_geocoding_failure(client, monkeypatch) -> None:
    def _boom(settings, location):
        raise RuntimeError("Nominatim unreachable")

    monkeypatch.setattr("app.services.sender_profile.geocode_point", _boom)
    payload = {
        "display_name": "Mario Rossi",
        "intro": "Ciao",
        "website_url": "https://example.test",
        "freelancer_links": [],
        "social_links": [],
        "other_links": [],
        "reference_location": "Zona sconosciuta",
        "local_radius_km": None,
        "local_mention_enabled": False,
        "local_mention_text": None,
    }
    response = client.put("/settings/profile", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["reference_location"] == "Zona sconosciuta"
    assert body["reference_latitude"] is None


def test_companies_sort_and_filter_by_distance(client, db_session) -> None:
    from app.services.sender_profile import get_or_create_sender_profile

    profile = get_or_create_sender_profile(db_session)
    profile.reference_latitude = 41.4622
    profile.reference_longitude = 15.5477
    db_session.commit()

    near = Company(
        name="Vicino SRL",
        category="ristorante",
        city="Foggia",
        latitude=41.46,
        longitude=15.55,
        source="manual",
        status="discovered",
    )
    far = Company(
        name="Lontano SRL",
        category="ristorante",
        city="Torino",
        latitude=45.07,
        longitude=7.69,
        source="manual",
        status="discovered",
    )
    db_session.add_all([near, far])
    db_session.commit()

    response = client.get("/companies?sort=distance")
    names = [item["name"] for item in response.json()]
    assert names.index("Vicino SRL") < names.index("Lontano SRL")

    filtered = client.get("/companies?sort=distance&max_distance_km=50")
    filtered_names = [item["name"] for item in filtered.json()]
    assert "Vicino SRL" in filtered_names
    assert "Lontano SRL" not in filtered_names


def _score(**kwargs):
    class Score:
        pass

    score = Score()
    for key, value in kwargs.items():
        setattr(score, key, value)
    return score


def test_proposal_email_mentions_concept_only_when_generated() -> None:
    score = _score(overall_score=40, opportunity_score=60, priority="MEDIUM", recommended_service="Restyling")
    without_concept = build_proposal_draft(
        domain="example.test",
        url="https://example.test",
        company_name="Esempio",
        city="Foggia",
        findings=[],
        website_score=score,
        opportunity_score=score,
        has_concept=False,
    )
    with_concept = build_proposal_draft(
        domain="example.test",
        url="https://example.test",
        company_name="Esempio",
        city="Foggia",
        findings=[],
        website_score=score,
        opportunity_score=score,
        has_concept=True,
    )
    assert "direzione per la homepage" not in without_concept.email_body
    assert "direzione per la homepage" in with_concept.email_body


def test_proposal_email_includes_local_mention_only_when_provided() -> None:
    score = _score(overall_score=40, opportunity_score=60, priority="MEDIUM", recommended_service="Restyling")
    without_mention = build_proposal_draft(
        domain="example.test",
        url="https://example.test",
        company_name="Esempio",
        city="Foggia",
        findings=[],
        website_score=score,
        opportunity_score=score,
        local_mention=None,
    )
    with_mention = build_proposal_draft(
        domain="example.test",
        url="https://example.test",
        company_name="Esempio",
        city="Foggia",
        findings=[],
        website_score=score,
        opportunity_score=score,
        local_mention="Possiamo vederci di persona.",
    )
    assert "Possiamo vederci di persona." not in without_mention.email_body
    assert "Possiamo vederci di persona." in with_mention.email_body


def test_sender_profile_view_defaults_have_no_local_mention() -> None:
    assert DEFAULT_SENDER.local_mention_enabled is False
    assert DEFAULT_SENDER.local_mention_text is None
    view = SenderProfileView(
        display_name="X",
        intro="Y",
        website_url="https://x.test",
        freelancer_links=(),
        social_links=(),
    )
    assert view.reference_latitude is None
