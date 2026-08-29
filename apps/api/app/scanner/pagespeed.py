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
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPError as exc:
        return {"ok": False, "error": str(exc)}

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
