import re
from collections import Counter
from urllib.parse import parse_qs, urlparse

import httpx

_APPLE_ID_PATH = re.compile(r"/id(\d+)", re.IGNORECASE)
_USER_AGENT = "RevampRadar/1.0 (+https://revampradar.local)"

_THEMES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("crash", "Crash / instabilità", ("crash", "crasha", "si chiude", "blocc", "freeze")),
    ("slow", "Lentezza", ("lento", "lenta", "slow", "lag", "hang")),
    ("booking", "Prenotazioni", ("prenot", "book", "reservation", "disponib")),
    ("pay", "Pagamenti", ("pagament", "payment", "stripe", "carta", "paypal", "rimborso")),
    ("login", "Accesso / account", ("login", "acced", "password", "account", "sign in")),
    ("notify", "Notifiche", ("notif", "push")),
    ("offline", "Offline / rete", ("offline", "connessione", "network", "wifi")),
    (
        "want_feature",
        "Richieste funzionali",
        ("vorrei", "manca", "aggiung", "please add", "wish", "dovrebbe", "sarebbe utile"),
    ),
)


def apple_app_id(url: str) -> str | None:
    parsed = urlparse(url)
    match = _APPLE_ID_PATH.search(parsed.path)
    if match:
        return match.group(1)
    values = parse_qs(parsed.query).get("id") or []
    if values and values[0].isdigit():
        return values[0]
    return None


def apple_store_country(url: str) -> str:
    parts = [part for part in urlparse(url).path.split("/") if part]
    if parts and len(parts[0]) == 2 and parts[0].isalpha():
        return parts[0].lower()
    return "it"


def play_package_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    if host != "play.google.com" and not host.endswith(".play.google.com"):
        return None
    values = parse_qs(parsed.query).get("id") or []
    package = values[0].strip() if values else ""
    return package or None


def fetch_apple_listing(url: str, timeout: float = 8.0) -> dict | None:
    app_id = apple_app_id(url)
    if app_id is None:
        return None
    try:
        response = httpx.get(
            "https://itunes.apple.com/lookup",
            params={"id": app_id},
            timeout=timeout,
            headers={"User-Agent": _USER_AGENT},
        )
        response.raise_for_status()
        results = response.json().get("results") or []
    except (httpx.HTTPError, ValueError):
        return None
    if not results or not isinstance(results[0], dict):
        return None
    item = results[0]
    rating = item.get("averageUserRating")
    count = item.get("userRatingCount")
    name = item.get("trackCensoredName") or item.get("trackName")
    return {
        "name": name if isinstance(name, str) else None,
        "version": item.get("version") if isinstance(item.get("version"), str) else None,
        "average_rating": round(float(rating), 2) if isinstance(rating, int | float) else None,
        "rating_count": int(count) if isinstance(count, int | float) else None,
        "source": "itunes_lookup",
    }


def fetch_apple_reviews(url: str, timeout: float = 8.0) -> dict | None:
    app_id = apple_app_id(url)
    if app_id is None:
        return None
    country = apple_store_country(url)
    feed_url = f"https://itunes.apple.com/{country}/rss/customerreviews/id={app_id}/sortBy=mostRecent/json"
    try:
        response = httpx.get(feed_url, timeout=timeout, headers={"User-Agent": _USER_AGENT})
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    return summarize_apple_reviews(payload, country)


def summarize_apple_reviews(payload: dict, country: str) -> dict | None:
    reviews = _parse_review_entries(payload)
    if not reviews:
        return None
    ratings = [item["rating"] for item in reviews if item["rating"] is not None]
    average = round(sum(ratings) / len(ratings), 2) if ratings else None
    positive = sum(1 for value in ratings if value >= 4)
    negative = sum(1 for value in ratings if value <= 2)
    return {
        "source": "apple_rss",
        "country": country,
        "fetched": len(reviews),
        "average_rating": average,
        "sentiment": _sentiment(average),
        "positive_count": positive,
        "negative_count": negative,
        "themes": _themes(reviews),
        "samples": [
            {"rating": item["rating"], "title": item["title"], "text": item["text"]}
            for item in reviews[:3]
        ],
    }


def enrich_app_links(
    links: list[dict],
    *,
    lookup=fetch_apple_listing,
    reviews=fetch_apple_reviews,
) -> list[dict]:
    enriched: list[dict] = []
    apple_lookups = 0
    for item in links:
        row = dict(item)
        if row.get("store") == "app_store" and apple_lookups < 2:
            listing = lookup(row.get("url") or "")
            apple_lookups += 1
            if listing:
                review_data = reviews(row.get("url") or "")
                if review_data:
                    listing = {**listing, "reviews": review_data}
                row["listing"] = listing
        elif row.get("store") == "play_store":
            package = play_package_id(row.get("url") or "")
            if package:
                row["listing"] = {
                    "name": None,
                    "version": None,
                    "average_rating": None,
                    "rating_count": None,
                    "package_id": package,
                    "source": "play_url",
                }
        enriched.append(row)
    return enriched


def _sentiment(average: float | None) -> str:
    if average is None:
        return "n/d"
    if average >= 4:
        return "positive"
    if average >= 3:
        return "mixed"
    return "negative"


def _themes(reviews: list[dict]) -> list[dict]:
    counts: Counter[str] = Counter()
    for review in reviews:
        blob = f"{review.get('title') or ''} {review.get('text') or ''}".lower()
        for code, _label, needles in _THEMES:
            if any(needle in blob for needle in needles):
                counts[code] += 1
    themes = []
    labels = {code: label for code, label, _needles in _THEMES}
    for code, count in counts.most_common(8):
        themes.append({"code": code, "label": labels[code], "count": count})
    return themes


def _parse_review_entries(payload: dict) -> list[dict]:
    feed = payload.get("feed") if isinstance(payload, dict) else None
    if not isinstance(feed, dict):
        return []
    raw = feed.get("entry")
    if isinstance(raw, dict):
        entries = [raw]
    elif isinstance(raw, list):
        entries = [item for item in raw if isinstance(item, dict)]
    else:
        return []
    reviews: list[dict] = []
    for entry in entries:
        rating_raw = _atom_label(entry.get("im:rating"))
        if rating_raw is None:
            continue
        try:
            rating = int(rating_raw)
        except (TypeError, ValueError):
            rating = None
        title = _atom_label(entry.get("title"))
        text = _atom_label(entry.get("content")) or ""
        text = " ".join(text.split())
        if len(text) > 400:
            text = text[:397] + "..."
        reviews.append({"rating": rating, "title": title, "text": text})
    return reviews


def _atom_label(node: object) -> str | None:
    if isinstance(node, str) and node.strip():
        return node.strip()
    if isinstance(node, dict):
        label = node.get("label")
        if isinstance(label, str) and label.strip():
            return label.strip()
    return None
