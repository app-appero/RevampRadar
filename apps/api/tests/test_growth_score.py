from app.scoring.greenfield import compute_growth_score, rating_from_osm_tags


def test_high_competition_gap_raises_score() -> None:
    draft = compute_growth_score(
        name="Trattoria da Mario",
        category="Ristorante",
        city="Palermo",
        phone="0911234567",
        email="info@example.test",
        rating=4.5,
        peer_total=10,
        peer_with_website=9,
    )
    assert draft.score >= 60
    assert draft.priority in {"HIGH", "VERY_HIGH"}
    assert any("simili" in reason or "%" in reason for reason in draft.top_reasons)
    assert draft.recommended_service == "Creazione sito vetrina con prenotazione online"


def test_low_digital_dependency_category_scores_lower_than_high() -> None:
    low = compute_growth_score(
        name="Idraulico Rossi",
        category="Idraulico",
        city="Torino",
        phone=None,
        email=None,
        rating=None,
        peer_total=0,
        peer_with_website=0,
    )
    high = compute_growth_score(
        name="Hotel Bella Vista",
        category="Hotel",
        city="Torino",
        phone="0111234567",
        email="info@example.test",
        rating=4.8,
        peer_total=10,
        peer_with_website=9,
    )
    assert low.score < high.score
    assert low.priority != "VERY_HIGH"


def test_no_peers_falls_back_to_neutral_competition_gap() -> None:
    draft = compute_growth_score(
        name="Studio Legale Bianchi",
        category="Avvocato",
        city="Bologna",
        phone="0512345678",
        email=None,
        rating=None,
        peer_total=0,
        peer_with_website=0,
    )
    assert draft.components["competition_gap"] == 50
    assert draft.peer_sample_size == 0
    assert 0 <= draft.confidence <= 0.75


def test_rating_from_osm_tags_reads_stars() -> None:
    assert rating_from_osm_tags({"osm_tags": {"stars": "4.5"}}) == 4.5
    assert rating_from_osm_tags({"osm_tags": {}}) is None
    assert rating_from_osm_tags(None) is None
    assert rating_from_osm_tags({"osm_tags": {"stars": "not-a-number"}}) is None
