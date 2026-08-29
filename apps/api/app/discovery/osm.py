from __future__ import annotations

import httpx

from app.config import Settings
from app.discovery.types import DiscoveryCandidate, DiscoveryQuery

_INDUSTRY_TAGS: dict[str, list[tuple[str, str]]] = {
    "hotel": [("tourism", "hotel")],
    "hotels": [("tourism", "hotel")],
    "albergo": [("tourism", "hotel")],
    "alberghi": [("tourism", "hotel")],
    "b&b": [("tourism", "guest_house")],
    "bb": [("tourism", "guest_house")],
    "guest house": [("tourism", "guest_house")],
    "ristorante": [("amenity", "restaurant")],
    "ristoranti": [("amenity", "restaurant")],
    "restaurant": [("amenity", "restaurant")],
    "bar": [("amenity", "bar")],
    "pizzeria": [("amenity", "restaurant")],
}


def industry_tags(industry: str) -> list[tuple[str, str]]:
    key = " ".join(industry.lower().split())
    if key in _INDUSTRY_TAGS:
        return _INDUSTRY_TAGS[key]
    if "hotel" in key or "alberg" in key:
        return [("tourism", "hotel")]
    if "ristor" in key or "restaurant" in key:
        return [("amenity", "restaurant")]
    return [("tourism", "hotel")]


class OpenStreetMapProvider:
    name = "openstreetmap"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def search_businesses(self, query: DiscoveryQuery) -> list[DiscoveryCandidate]:
        area = self._resolve_area(query.location)
        tags = industry_tags(query.industry)
        fetch_limit = min(100, max(query.max_results * 5, 25))
        elements = self._overpass(area, tags, fetch_limit)
        candidates: list[DiscoveryCandidate] = []
        for element in elements:
            candidate = _from_osm(element, query.industry)
            if candidate is not None:
                candidates.append(candidate)
        candidates.sort(key=lambda item: (item.website_url is None, item.name.lower()))
        return candidates[: query.max_results]

    def _resolve_area(self, location: str) -> dict:
        url = self._settings.nominatim_url.rstrip("/") + "/search"
        headers = {"User-Agent": self._settings.scanner_user_agent, "Accept": "application/json"}
        timeout = httpx.Timeout(self._settings.discovery_timeout_seconds)
        with httpx.Client(timeout=timeout, headers=headers) as client:
            response = client.get(
                url,
                params={"q": location, "format": "json", "limit": 1, "addressdetails": 1},
            )
        if response.status_code >= 400:
            raise RuntimeError(f"Nominatim HTTP {response.status_code}")
        payload = response.json()
        if not payload:
            raise RuntimeError(f"Località non trovata: {location}")
        item = payload[0]
        osm_type = item.get("osm_type")
        osm_id = item.get("osm_id")
        if osm_type not in {"relation", "way", "node"} or not osm_id:
            raise RuntimeError("Nominatim non ha restituito un'area OSM valida.")
        prefix = {"relation": 3600000000, "way": 2400000000, "node": 0}[osm_type]
        return {
            "area_id": prefix + int(osm_id) if prefix else None,
            "bbox": item.get("boundingbox"),
            "display_name": item.get("display_name"),
        }

    def _overpass(self, area: dict, tags: list[tuple[str, str]], limit: int) -> list[dict]:
        filters = "".join(f'nwr["{key}"="{value}"](area.searchArea);' for key, value in tags)
        area_id = area.get("area_id")
        if area_id:
            query = (
                f"[out:json][timeout:{int(self._settings.discovery_timeout_seconds)}];"
                f"area({area_id})->.searchArea;({filters});out tags center {limit};"
            )
        else:
            bbox = area.get("bbox") or []
            if len(bbox) != 4:
                raise RuntimeError("Bounding box OSM non disponibile.")
            south, north, west, east = bbox
            bbox_filters = "".join(
                f'nwr["{key}"="{value}"]({south},{west},{north},{east});' for key, value in tags
            )
            query = (
                f"[out:json][timeout:{int(self._settings.discovery_timeout_seconds)}];"
                f"({bbox_filters});out tags center {limit};"
            )
        headers = {"User-Agent": self._settings.scanner_user_agent}
        timeout = httpx.Timeout(self._settings.discovery_timeout_seconds + 5)
        with httpx.Client(timeout=timeout, headers=headers) as client:
            response = client.post(self._settings.overpass_url, data={"data": query})
        if response.status_code >= 400:
            raise RuntimeError(f"Overpass HTTP {response.status_code}: {response.text[:300]}")
        payload = response.json()
        return payload.get("elements") or []


def _from_osm(element: dict, industry: str) -> DiscoveryCandidate | None:
    tags = element.get("tags") or {}
    name = tags.get("name")
    if not name:
        return None
    website = tags.get("website") or tags.get("contact:website") or tags.get("url")
    osm_type = element.get("type", "node")
    osm_id = element.get("id")
    return DiscoveryCandidate(
        name=name,
        category=industry,
        city=tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:village"),
        region=tags.get("addr:province") or tags.get("addr:state"),
        country=tags.get("addr:country") or "IT",
        website_url=website,
        phone=tags.get("phone") or tags.get("contact:phone"),
        email=tags.get("email") or tags.get("contact:email"),
        source="openstreetmap",
        external_id=f"{osm_type}/{osm_id}" if osm_id is not None else None,
        extra={"osm_tags": {key: tags[key] for key in ("tourism", "amenity", "stars") if key in tags}},
    )
