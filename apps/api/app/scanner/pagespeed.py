import httpx

from app.config import Settings


def fetch_pagespeed(url: str, settings: Settings) -> dict | None:
    if not settings.pagespeed_api_key:
        return None

    endpoint = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    params = {
        "url": url,
        "key": settings.pagespeed_api_key,
        "strategy": "mobile",
        "category": ["PERFORMANCE", "ACCESSIBILITY", "BEST_PRACTICES", "SEO"],
    }
    try:
        response = httpx.get(endpoint, params=params, timeout=30.0)
    except httpx.HTTPError:
        # Niente str(exc): httpx la costruisce includendo l'URL della richiesta,
        # che qui contiene la chiave PageSpeed nella query string.
        return {"ok": False, "error": "pagespeed_network_error"}
    if response.status_code >= 400:
        return {"ok": False, "error": f"pagespeed_http_{response.status_code}"}
    try:
        payload = response.json()
    except ValueError:
        return {"ok": False, "error": "pagespeed_invalid_response"}

    categories = payload.get("lighthouseResult", {}).get("categories", {})
    audits = payload.get("lighthouseResult", {}).get("audits", {})

    def score(name: str) -> int | None:
        raw = categories.get(name, {}).get("score")
        return int(raw * 100) if isinstance(raw, int | float) else None

    vitals = {}
    for key in ("largest-contentful-paint", "cumulative-layout-shift", "interaction-to-next-paint"):
        item = audits.get(key, {})
        vitals[key] = item.get("displayValue")

    return {
        "ok": True,
        "performance": score("performance"),
        "accessibility": score("accessibility"),
        "best_practices": score("best-practices"),
        "seo": score("seo"),
        "core_web_vitals": vitals,
        "source": "pagespeed",
    }
