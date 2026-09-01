from app.services.app_store import (
    apple_app_id,
    apple_store_country,
    enrich_app_links,
    fetch_apple_listing,
    play_package_id,
    summarize_apple_reviews,
)


def test_apple_app_id_from_path_and_query() -> None:
    assert apple_app_id("https://apps.apple.com/it/app/hotelsole/id310633997") == "310633997"
    assert apple_app_id("https://itunes.apple.com/lookup?id=12345") == "12345"
    assert apple_app_id("https://play.google.com/store/apps/details?id=it.hotel") is None


def test_fetch_apple_listing_parses_itunes(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "results": [
                    {
                        "trackName": "Hotel Sole",
                        "version": "3.2.1",
                        "averageUserRating": 4.35,
                        "userRatingCount": 128,
                    }
                ]
            }

    monkeypatch.setattr("app.services.app_store.httpx.get", lambda *args, **kwargs: FakeResponse())
    listing = fetch_apple_listing("https://apps.apple.com/app/id310633997")
    assert listing is not None
    assert listing["name"] == "Hotel Sole"
    assert listing["average_rating"] == 4.35
    assert listing["rating_count"] == 128
    assert listing["source"] == "itunes_lookup"


def test_enrich_app_links_looks_up_apple_only() -> None:
    links = [
        {"store": "play_store", "url": "https://play.google.com/store/apps/details?id=it.x"},
        {"store": "app_store", "url": "https://apps.apple.com/app/id1"},
    ]
    enriched = enrich_app_links(
        links,
        lookup=lambda url: {"name": "Sole", "source": "itunes_lookup"},
        reviews=lambda url: None,
    )
    assert enriched[0]["listing"]["package_id"] == "it.x"
    assert enriched[0]["listing"]["source"] == "play_url"
    assert enriched[1]["listing"]["name"] == "Sole"
    assert "reviews" not in enriched[1]["listing"]

    with_reviews = enrich_app_links(
        [{"store": "app_store", "url": "https://apps.apple.com/it/app/x/id1"}],
        lookup=lambda url: {"name": "Sole", "source": "itunes_lookup"},
        reviews=lambda url: {
            "source": "apple_rss",
            "country": "it",
            "fetched": 1,
            "average_rating": 4.0,
            "sentiment": "positive",
            "positive_count": 1,
            "negative_count": 0,
            "themes": [],
            "samples": [],
        },
    )
    assert with_reviews[0]["listing"]["reviews"]["source"] == "apple_rss"


def test_apple_store_country() -> None:
    assert apple_store_country("https://apps.apple.com/it/app/hotelsole/id1") == "it"
    assert apple_store_country("https://apps.apple.com/app/id1") == "it"
    assert apple_store_country("https://apps.apple.com/us/app/x/id1") == "us"


def test_summarize_apple_reviews_sentiment_and_themes() -> None:
    payload = {
        "feed": {
            "entry": [
                {"title": {"label": "App"}, "content": {"label": "metadata"}},
                {
                    "im:rating": {"label": "1"},
                    "title": {"label": "Si chiude"},
                    "content": {"label": "Crash continuo, vorrei le notifiche push."},
                },
                {
                    "im:rating": {"label": "5"},
                    "title": {"label": "Ok"},
                    "content": {"label": "Tutto bene."},
                },
                {
                    "im:rating": {"label": "2"},
                    "title": {"label": "Lenta"},
                    "content": {"label": "App lenta e pagamenti che falliscono."},
                },
            ]
        }
    }
    summary = summarize_apple_reviews(payload, "it")
    assert summary is not None
    assert summary["fetched"] == 3
    assert summary["source"] == "apple_rss"
    assert summary["sentiment"] == "negative"
    assert summary["negative_count"] == 2
    assert summary["positive_count"] == 1
    codes = {item["code"] for item in summary["themes"]}
    assert "crash" in codes
    assert "want_feature" in codes
    assert "pay" in codes
    assert "slow" in codes
    assert len(summary["samples"]) == 3


def test_summarize_skips_empty_feed() -> None:
    assert summarize_apple_reviews({"feed": {"entry": []}}, "it") is None


def test_play_package_id() -> None:
    assert play_package_id("https://play.google.com/store/apps/details?id=it.hotel") == "it.hotel"
    assert play_package_id("https://apps.apple.com/app/id1") is None
