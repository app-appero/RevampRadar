from uuid import uuid4

from app.services.geo_cluster import GeoMember, choose_k, cluster_members, kmeans


def test_choose_k() -> None:
    assert choose_k(0) == 1
    assert choose_k(2) == 1
    assert choose_k(4) == 2
    assert choose_k(9) == 3
    assert choose_k(50) == 6


def test_kmeans_separates_distant_cities() -> None:
    palermo = (38.1157, 13.3615)
    catania = (37.5079, 15.0830)
    milan = (45.4642, 9.1900)
    coords = [palermo, palermo, catania, milan, milan, milan]
    labels = kmeans(coords, 2)
    assert len(set(labels)) == 2
    sicily = {labels[0], labels[1], labels[2]}
    north = {labels[3], labels[4], labels[5]}
    assert len(sicily) == 1
    assert len(north) == 1
    assert sicily != north


def test_cluster_summary_is_descriptive() -> None:
    palermo = GeoMember(
        company_id=uuid4(),
        name="Hotel Sole",
        latitude=38.1157,
        longitude=13.3615,
        city="Palermo",
        category="Hotel",
        opportunity_score=80,
        website_score=40,
        priority="HIGH",
        has_app=False,
        has_website=True,
    )
    milan = GeoMember(
        company_id=uuid4(),
        name="Hotel Duomo",
        latitude=45.4642,
        longitude=9.1900,
        city="Milano",
        category="Hotel",
        opportunity_score=40,
        website_score=70,
        priority="LOW",
        has_app=True,
        has_website=True,
    )
    clusters = cluster_members([palermo, milan, milan])
    assert len(clusters) >= 1
    assert all("Hotel" in item.label for item in clusters)
    assert all("accett" not in item.label.lower() for item in clusters)
    assert all(item.no_site_share == 0 for item in clusters)
    assert all("senza sito" not in item.label for item in clusters)


def test_cluster_flags_companies_without_website() -> None:
    with_site = GeoMember(
        company_id=uuid4(),
        name="Hotel Sole",
        latitude=38.1157,
        longitude=13.3615,
        city="Palermo",
        category="Hotel",
        opportunity_score=40,
        website_score=40,
        priority="LOW",
        has_app=False,
        has_website=True,
    )
    without_site = GeoMember(
        company_id=uuid4(),
        name="Baia",
        latitude=38.116,
        longitude=13.362,
        city="Palermo",
        category="Hotel",
        opportunity_score=None,
        website_score=None,
        priority=None,
        has_app=False,
        has_website=False,
    )
    clusters = cluster_members([with_site, without_site])
    assert len(clusters) == 1
    assert clusters[0].no_site_share == 0.5
    assert "molti senza sito" in clusters[0].label
