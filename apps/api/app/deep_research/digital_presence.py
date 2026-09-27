"""Presenza digitale consolidata: estende l'intelligence esistente (OSM + HTML),
non introduce nuovo scraping. Ogni canale riporta trovato/url/fonte.
"""

from __future__ import annotations

from app.discovery.osm import social_contact_links
from app.models.entities import Company

_NAMED_CHANNELS = (
    "website",
    "instagram",
    "facebook",
    "tiktok",
    "youtube",
    "linkedin",
    "app_store",
    "google_play",
)

_OSM_LABEL_TO_CHANNEL = {
    "facebook": "facebook",
    "instagram": "instagram",
    "tiktok": "tiktok",
    "youtube": "youtube",
}


def build_digital_presence(company: Company, html_data: dict | None) -> dict:
    channels: dict[str, dict] = {
        name: {"found": False, "url": None, "source": None} for name in _NAMED_CHANNELS
    }
    extra_found: list[dict] = []

    if company.website_url:
        channels["website"] = {"found": True, "url": company.website_url, "source": "azienda"}

    tags = _osm_tags(company)
    for label, url in social_contact_links(tags):
        channel = _OSM_LABEL_TO_CHANNEL.get(label.lower())
        if channel is not None:
            if not channels[channel]["found"]:
                channels[channel] = {"found": True, "url": url, "source": "osm"}
        else:
            extra_found.append({"network": label, "url": url, "source": "osm"})

    if html_data:
        for item in html_data.get("social_links") or []:
            network = item.get("network")
            url = item.get("url")
            if network in channels:
                if not channels[network]["found"]:
                    channels[network] = {"found": True, "url": url, "source": "sito"}
            elif network:
                extra_found.append({"network": network, "url": url, "source": "sito"})
        for item in html_data.get("app_links") or []:
            store = item.get("store")
            url = item.get("url")
            if store in channels and not channels[store]["found"]:
                channels[store] = {"found": True, "url": url, "source": "sito"}

    return {"channels": channels, "other": extra_found}


def _osm_tags(company: Company) -> dict | None:
    extra = company.extra or {}
    tags = extra.get("osm_tags")
    if not isinstance(tags, dict) or not tags:
        return None
    return tags
