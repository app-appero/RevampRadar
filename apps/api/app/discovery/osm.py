from __future__ import annotations

import re
import time
from collections.abc import Callable

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
    "bed and breakfast": [("tourism", "guest_house")],
    "guest house": [("tourism", "guest_house")],
    "agriturismo": [("tourism", "guest_house"), ("tourism", "apartment")],
    "ostello": [("tourism", "hostel")],
    "camping": [("tourism", "camp_site")],
    "campeggio": [("tourism", "camp_site")],
    "ristorante": [("amenity", "restaurant")],
    "ristoranti": [("amenity", "restaurant")],
    "restaurant": [("amenity", "restaurant")],
    "trattoria": [("amenity", "restaurant")],
    "osteria": [("amenity", "restaurant")],
    "pizzeria": [("amenity", "restaurant"), ("amenity", "fast_food")],
    "bar": [("amenity", "bar"), ("amenity", "cafe")],
    "caffè": [("amenity", "cafe")],
    "caffe": [("amenity", "cafe")],
    "cafe": [("amenity", "cafe")],
    "gelateria": [("amenity", "ice_cream")],
    "panificio": [("shop", "bakery")],
    "panetteria": [("shop", "bakery")],
    "pasticceria": [("shop", "pastry"), ("shop", "bakery")],
    "macelleria": [("shop", "butcher")],
    "pescheria": [("shop", "seafood")],
    "barbiere": [("shop", "hairdresser"), ("craft", "hairdresser")],
    "barbieri": [("shop", "hairdresser"), ("craft", "hairdresser")],
    "parrucchiere": [("shop", "hairdresser")],
    "parrucchieri": [("shop", "hairdresser")],
    "hairdresser": [("shop", "hairdresser")],
    "estetista": [("shop", "beauty")],
    "centro estetico": [("shop", "beauty")],
    "farmacia": [("amenity", "pharmacy")],
    "dentista": [("amenity", "dentist")],
    "medico": [("amenity", "doctors"), ("amenity", "clinic")],
    "veterinario": [("amenity", "veterinary")],
    "fisioterapista": [("healthcare", "physiotherapist")],
    "palestra": [("leisure", "fitness_centre"), ("leisure", "sports_centre")],
    "ferramenta": [("shop", "hardware"), ("shop", "doityourself")],
    "abbigliamento": [("shop", "clothes")],
    "supermercato": [("shop", "supermarket")],
    "alimentari": [("shop", "convenience"), ("shop", "supermarket")],
    "fiorista": [("shop", "florist")],
    "fioraio": [("shop", "florist")],
    "ottico": [("shop", "optician")],
    "gioielleria": [("shop", "jewelry")],
    "libreria": [("shop", "books")],
    "edicola": [("shop", "newsagent")],
    "tabacchi": [("shop", "tobacco")],
    "arredamento": [("shop", "furniture")],
    "meccanico": [("shop", "car_repair")],
    "officina": [("shop", "car_repair")],
    "autofficina": [("shop", "car_repair")],
    "carrozzeria": [("shop", "car_repair")],
    "elettricista": [("craft", "electrician")],
    "idraulico": [("craft", "plumber")],
    "falegname": [("craft", "carpenter"), ("craft", "joiner")],
    "fabbro": [("craft", "locksmith")],
    "avvocato": [("office", "lawyer")],
    "commercialista": [("office", "accountant"), ("office", "tax_advisor")],
    "agenzia immobiliare": [("office", "estate_agent")],
    "immobiliare": [("office", "estate_agent")],
    "assicurazioni": [("office", "insurance")],
    "assicurazione": [("office", "insurance")],
    "notaio": [("office", "notary")],
    "agenzia viaggi": [("shop", "travel_agency")],
    "benzinaio": [("amenity", "fuel")],
    "scuola guida": [("amenity", "driving_school")],
    "autoscuola": [("amenity", "driving_school")],
    "lavanderia": [("shop", "laundry")],
    "lavasecco": [("shop", "dry_cleaning"), ("shop", "laundry")],
    "fotografo": [("shop", "photo"), ("craft", "photographer")],
    "enoteca": [("shop", "wine"), ("amenity", "bar")],
    "pub": [("amenity", "pub")],
    "fast food": [("amenity", "fast_food")],
    "kebab": [("amenity", "fast_food")],
    "gastronomia": [("shop", "deli")],
    "forno": [("shop", "bakery")],
    "unghie": [("shop", "beauty")],
    "tatuatore": [("shop", "tattoo")],
    "centro benessere": [("leisure", "spa"), ("amenity", "spa")],
    "spa": [("leisure", "spa")],
    "parafarmacia": [("shop", "chemist"), ("amenity", "pharmacy")],
    "psicologo": [("healthcare", "psychotherapist"), ("office", "therapist")],
    "gommista": [("shop", "tyres")],
    "autolavaggio": [("amenity", "car_wash")],
    "concessionario": [("shop", "car")],
    "carrozziere": [("shop", "car_repair")],
    "imbianchino": [("craft", "painter")],
    "muratore": [("craft", "builder")],
    "geometra": [("office", "surveyor"), ("office", "architect")],
    "architetto": [("office", "architect")],
    "impresa edile": [("office", "construction_company")],
    "calzature": [("shop", "shoes")],
    "elettronica": [("shop", "electronics")],
    "telefonia": [("shop", "mobile_phone")],
    "informatica": [("shop", "computer")],
    "cartoleria": [("shop", "stationery")],
    "giocattoli": [("shop", "toys")],
    "pet shop": [("shop", "pet")],
    "negozio animali": [("shop", "pet")],
    "agenzia funebre": [("shop", "funeral_directors")],
    "copisteria": [("shop", "copyshop")],
    "tipografia": [("craft", "printmaker"), ("shop", "copyshop")],
    "piscina": [("leisure", "swimming_pool")],
    "cinema": [("amenity", "cinema")],
    "consulente del lavoro": [("office", "employment_agency"), ("office", "tax_advisor")],
    "caf": [("office", "tax_advisor")],
    "dentisti": [("amenity", "dentist")],
    "ottica": [("shop", "optician")],
}

_SUBSTRING_TAGS: tuple[tuple[tuple[str, ...], list[tuple[str, str]]], ...] = (
    (("hotel", "alberg"), [("tourism", "hotel")]),
    (("ristor", "restaurant", "trattor"), [("amenity", "restaurant")]),
    (("barber", "barbiere", "parrucch"), [("shop", "hairdresser"), ("craft", "hairdresser")]),
    (("farmac", "pharmacy"), [("amenity", "pharmacy")]),
    (("dentist",), [("amenity", "dentist")]),
    (("pizz",), [("amenity", "restaurant"), ("amenity", "fast_food")]),
    (("palestr", "fitness", "gym"), [("leisure", "fitness_centre")]),
    (("meccan", "officina", "carrozzer"), [("shop", "car_repair")]),
    (("gommist",), [("shop", "tyres")]),
    (("idraul",), [("craft", "plumber")]),
    (("elettric",), [("craft", "electrician")]),
)

_COMMERCIAL_KEYS = ("shop", "craft", "amenity", "tourism", "office", "leisure", "healthcare")
_SOCIAL_KEYS = (
    "contact:whatsapp", "whatsapp",
    "contact:facebook", "facebook",
    "contact:instagram", "instagram",
    "contact:telegram", "telegram",
    "contact:tiktok", "tiktok",
    "contact:twitter", "twitter", "contact:x",
    "contact:youtube", "youtube",
)
_OSM_EXTERNAL = re.compile(r"^(node|way|relation)/(\d+)$", re.IGNORECASE)
_OSM_REF_PREFIX = {"node": "N", "way": "W", "relation": "R"}
_DEFAULT_OVERPASS = (
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
)


def industry_tags(industry: str) -> list[tuple[str, str]]:
    key = " ".join(industry.lower().split())
    if key in _INDUSTRY_TAGS:
        return _INDUSTRY_TAGS[key]
    if "=" in key:
        left, right = (part.strip() for part in key.split("=", 1))
        if left in _COMMERCIAL_KEYS and right:
            return [(left, right)]
    for needles, tags in _SUBSTRING_TAGS:
        if any(needle in key for needle in needles):
            return tags
    for tags in _INDUSTRY_TAGS.values():
        for osm_key, osm_value in tags:
            if key == osm_value:
                return [(osm_key, osm_value)]
    return []


def industry_name_regex(industry: str) -> str | None:
    if industry_tags(industry):
        return None
    compact = re.sub(r"[^\wàèéìòù\- ]+", " ", industry.lower(), flags=re.IGNORECASE)
    compact = " ".join(compact.split())
    if len(compact) < 3:
        return None
    return re.escape(compact)


def format_industry_tags(industry: str) -> list[str]:
    out: list[str] = []
    for key, value in resolve_search_tags(industry):
        out.append(key if value == "*" else f"{key}={value}")
    return out


def is_universal_industry(industry: str) -> bool:
    return industry.strip().lower() in {"", "tutti", "tutti i settori"}


def resolve_search_tags(industry: str) -> list[tuple[str, str]]:
    if is_universal_industry(industry):
        return [(key, "*") for key in _COMMERCIAL_KEYS]
    return industry_tags(industry)


def listed_sectors() -> list[str]:
    seen: set[tuple[tuple[str, str], ...]] = set()
    names: list[str] = []
    for name, tags in _INDUSTRY_TAGS.items():
        fingerprint = tuple(tags)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        names.append(name)
    return names


def preview_industry(industry: str) -> dict:
    tags = format_industry_tags(industry)
    sectors = listed_sectors()
    mapped = is_universal_industry(industry) or bool(industry_tags(industry))
    return {
        "industry": industry.strip(),
        "mapped": mapped,
        "tags": tags,
        "examples": sectors[:8],
        "sectors": sectors,
    }


def empty_search_message(industry: str, location: str) -> str:
    if is_universal_industry(industry):
        return (
            f"Nessuna attività commerciale trovata a {location.strip() or 'Italia'}. "
            "Prova una città più piccola o un settore specifico."
        )
    preview = preview_industry(industry)
    if not preview["mapped"]:
        examples = ", ".join(preview["examples"])
        return (
            f"Nessun risultato: «{industry.strip()}» non corrisponde a un tag OpenStreetMap noto. "
            f"Prova un settore mappato (es. {examples}). Non vengono mostrati altri settori."
        )
    return (
        f"Nessun «{industry.strip()}» trovato a {location.strip()} "
        f"(tag OSM: {', '.join(preview['tags'])}). Non sono stati inclusi altri settori."
    )


def candidate_matches_industry(candidate: DiscoveryCandidate, industry: str) -> bool:
    mapped = resolve_search_tags(industry)
    if not mapped:
        return False
    extra = (candidate.extra or {}).get("osm_tags") or {}
    if not isinstance(extra, dict):
        return False
    for key, value in mapped:
        if value == "*":
            if extra.get(key):
                return True
        elif extra.get(key) == value:
            return True
    return False


def select_candidates(candidates: list[DiscoveryCandidate], query: DiscoveryQuery) -> list[DiscoveryCandidate]:
    named = [item for item in candidates if item.name]
    if not query.include_without_website:
        with_site = [item for item in named if item.website_url]
        named = with_site or named
    named.sort(key=lambda item: (item.website_url is None, item.name.lower()))
    return named[: query.max_results]


def parse_osm_external_id(external_id: str | None) -> tuple[str, int] | None:
    if not external_id:
        return None
    match = _OSM_EXTERNAL.fullmatch(external_id.strip())
    if not match:
        return None
    return match.group(1).lower(), int(match.group(2))


def overpass_error_message(status: int, body: str) -> str:
    text = body or ""
    if status in {429, 502, 503, 504} or "timeout" in text.lower() or "gateway" in text.lower():
        return (
            "Overpass è sovraccarico o in timeout. "
            "Riprova tra un minuto, oppure cerca una città (es. Palermo) invece di un'intera regione."
        )
    if "<" in text[:240]:
        return f"Overpass HTTP {status}."
    snippet = " ".join(text.split())[:180]
    return f"Overpass HTTP {status}" + (f": {snippet}" if snippet else ".")


def overpass_endpoints(settings: Settings) -> list[str]:
    seen: list[str] = []
    for raw in (settings.overpass_url, *settings.overpass_urls.split(","), *_DEFAULT_OVERPASS):
        url = raw.strip()
        if url and url not in seen:
            seen.append(url)
    return seen


class OpenStreetMapProvider:
    name = "openstreetmap"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def search_businesses(
        self,
        query: DiscoveryQuery,
        on_stage: Callable[[str], None] | None = None,
    ) -> list[DiscoveryCandidate]:
        tags = resolve_search_tags(query.industry)
        if not tags:
            return []
        if on_stage:
            on_stage("Ricerca località")
        area = self._resolve_area(query.location)
        fetch_limit = min(400, max(query.max_results * 2, 25))
        elements: list[dict] = []
        overpass_error: str | None = None
        if on_stage:
            on_stage("Query Overpass")
        try:
            elements = self._overpass(area, tags, fetch_limit)
        except RuntimeError as exc:
            overpass_error = str(exc)
        matched: list[DiscoveryCandidate] = []
        for item in elements:
            candidate = _from_osm(item, query.industry)
            if candidate is not None and candidate_matches_industry(candidate, query.industry):
                matched.append(candidate)
        found = select_candidates(matched, query)
        if found:
            return found
        if overpass_error:
            raise RuntimeError(overpass_error)
        return []

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

    def _overpass(
        self,
        area: dict,
        tags: list[tuple[str, str]],
        limit: int,
        *,
        name_regex: str | None = None,
    ) -> list[dict]:
        timeout_s = min(25, int(self._settings.discovery_timeout_seconds))
        query = _build_overpass_query(area, tags, limit, timeout_s, name_regex=name_regex)
        last_error: RuntimeError | None = None
        empty_ok = False
        http_timeout = httpx.Timeout(connect=10.0, read=float(timeout_s + 10), write=10.0, pool=10.0)
        headers = {"User-Agent": self._settings.scanner_user_agent}
        for url in overpass_endpoints(self._settings):
            try:
                with httpx.Client(timeout=http_timeout, headers=headers) as client:
                    response = client.post(url, data={"data": query})
            except httpx.TimeoutException:
                last_error = RuntimeError(overpass_error_message(504, "timeout"))
                continue
            if response.status_code >= 400:
                last_error = RuntimeError(overpass_error_message(response.status_code, response.text))
                continue
            try:
                payload = response.json()
            except ValueError:
                last_error = RuntimeError(overpass_error_message(response.status_code, response.text))
                continue
            elements = payload.get("elements") or []
            if elements:
                return elements
            empty_ok = True
        if empty_ok:
            return []
        if last_error:
            raise last_error
        return []

    def _nominatim_search(self, query: DiscoveryQuery, area: dict) -> list[DiscoveryCandidate]:
        bbox = area.get("bbox") or []
        if len(bbox) != 4:
            return []
        south, north, west, east = bbox
        time.sleep(1.05)
        url = self._settings.nominatim_url.rstrip("/") + "/search"
        headers = {"User-Agent": self._settings.scanner_user_agent, "Accept": "application/json"}
        timeout = httpx.Timeout(self._settings.discovery_timeout_seconds)
        with httpx.Client(timeout=timeout, headers=headers) as client:
            response = client.get(
                url,
                params={
                    "q": query.industry,
                    "format": "jsonv2",
                    "addressdetails": 1,
                    "extratags": 1,
                    "limit": min(50, query.max_results),
                    "countrycodes": "it",
                    "viewbox": f"{west},{north},{east},{south}",
                    "bounded": 1,
                },
            )
        if response.status_code >= 400:
            raise RuntimeError(f"Nominatim HTTP {response.status_code}")
        payload = response.json()
        if not isinstance(payload, list):
            return []
        found = [_from_nominatim(item, query.industry) for item in payload]
        return [item for item in found if item is not None]


def fetch_coords_for_external_ids(settings: Settings, external_ids: list[str]) -> dict[str, tuple[float, float]]:
    parsed: list[tuple[str, str, int]] = []
    for external_id in external_ids:
        item = parse_osm_external_id(external_id)
        if item is None:
            continue
        parsed.append((external_id, item[0], item[1]))
    if not parsed:
        return {}
    coords = _overpass_coords_by_id(settings, parsed)
    missing = [item for item in parsed if item[0] not in coords]
    if missing:
        coords.update(_nominatim_lookup_coords(settings, missing))
    return coords


def _build_overpass_query(
    area: dict,
    tags: list[tuple[str, str]],
    limit: int,
    timeout: int,
    *,
    name_regex: str | None = None,
) -> str:
    bbox = area.get("bbox") or []
    if len(bbox) == 4:
        south, north, west, east = bbox
        geo = f"({south},{west},{north},{east})"
        parts = _overpass_filters(tags, name_regex, geo)
        return f"[out:json][timeout:{timeout}];({''.join(parts)});out center {limit};"
    area_id = area.get("area_id")
    if not area_id:
        raise RuntimeError("Bounding box OSM non disponibile.")
    parts = _overpass_filters(tags, name_regex, "(area.searchArea)")
    return (
        f"[out:json][timeout:{timeout}];"
        f"area({area_id})->.searchArea;({''.join(parts)});out center {limit};"
    )


def _overpass_filters(tags: list[tuple[str, str]], name_regex: str | None, geo: str) -> list[str]:
    parts: list[str] = []
    for key, value in tags:
        if value == "*":
            parts.append(f'node["{key}"]{geo};')
            parts.append(f'way["{key}"]{geo};')
        else:
            parts.append(f'node["{key}"="{value}"]{geo};')
            parts.append(f'way["{key}"="{value}"]{geo};')
    if name_regex:
        for key in _COMMERCIAL_KEYS:
            parts.append(f'node["name"~"{name_regex}",i]["{key}"]{geo};')
            parts.append(f'way["name"~"{name_regex}",i]["{key}"]{geo};')
            parts.append(f'node["{key}"~"{name_regex}",i]{geo};')
            parts.append(f'way["{key}"~"{name_regex}",i]{geo};')
    if not parts:
        raise RuntimeError("Settore non traducibile in una query OpenStreetMap.")
    return parts


def _overpass_coords_by_id(
    settings: Settings, parsed: list[tuple[str, str, int]]
) -> dict[str, tuple[float, float]]:
    nodes = [str(osm_id) for _, osm_type, osm_id in parsed if osm_type == "node"]
    ways = [str(osm_id) for _, osm_type, osm_id in parsed if osm_type == "way"]
    rels = [str(osm_id) for _, osm_type, osm_id in parsed if osm_type == "relation"]
    parts: list[str] = []
    if nodes:
        parts.append(f"node(id:{','.join(nodes)});")
    if ways:
        parts.append(f"way(id:{','.join(ways)});")
    if rels:
        parts.append(f"relation(id:{','.join(rels)});")
    query = f"[out:json][timeout:20];({''.join(parts)});out center;"
    http_timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0)
    headers = {"User-Agent": settings.scanner_user_agent}
    for url in overpass_endpoints(settings):
        try:
            with httpx.Client(timeout=http_timeout, headers=headers) as client:
                response = client.post(url, data={"data": query})
        except httpx.TimeoutException:
            continue
        if response.status_code >= 400:
            continue
        try:
            payload = response.json()
        except ValueError:
            continue
        found: dict[str, tuple[float, float]] = {}
        for element in payload.get("elements") or []:
            osm_type = element.get("type")
            osm_id = element.get("id")
            coords = element_coords(element)
            if osm_type and osm_id is not None and coords:
                found[f"{osm_type}/{osm_id}"] = coords
        if found:
            return found
    return {}


def _nominatim_lookup_coords(
    settings: Settings, parsed: list[tuple[str, str, int]]
) -> dict[str, tuple[float, float]]:
    found: dict[str, tuple[float, float]] = {}
    headers = {"User-Agent": settings.scanner_user_agent, "Accept": "application/json"}
    url = settings.nominatim_url.rstrip("/") + "/lookup"
    timeout = httpx.Timeout(30.0)
    batch_size = 50
    for index in range(0, len(parsed), batch_size):
        if index:
            time.sleep(1.05)
        chunk = parsed[index : index + batch_size]
        osm_ids = ",".join(f"{_OSM_REF_PREFIX[osm_type]}{osm_id}" for _, osm_type, osm_id in chunk)
        with httpx.Client(timeout=timeout, headers=headers) as client:
            response = client.get(url, params={"osm_ids": osm_ids, "format": "json"})
        if response.status_code >= 400:
            continue
        try:
            payload = response.json()
        except ValueError:
            continue
        if not isinstance(payload, list):
            continue
        for item in payload:
            osm_type = item.get("osm_type")
            osm_id = item.get("osm_id")
            coords = element_coords(item)
            if osm_type and osm_id is not None and coords:
                found[f"{osm_type}/{osm_id}"] = coords
    return found


def element_coords(element: dict) -> tuple[float, float] | None:
    lat = element.get("lat")
    lon = element.get("lon")
    if lat is None or lon is None:
        center = element.get("center") or {}
        lat = center.get("lat")
        lon = center.get("lon")
    from app.discovery.normalize import normalize_coords

    return normalize_coords(lat, lon)


def _osm_extra(tags: dict) -> dict:
    keys = (*_COMMERCIAL_KEYS, *_SOCIAL_KEYS, "stars", "start_date", "opening_hours")
    return {
        "osm_tags": {key: tags[key] for key in keys if key in tags},
    }


def _phone_from_tags(tags: dict) -> str | None:
    return tags.get("phone") or tags.get("contact:phone") or tags.get("contact:mobile") or tags.get("mobile")


def social_contact_links(osm_tags: dict | None) -> list[tuple[str, str]]:
    """Tutti i contatti social (label, url) trovati nei tag OSM, non solo il migliore."""
    if not osm_tags:
        return []
    links: list[tuple[str, str]] = []

    whatsapp = osm_tags.get("contact:whatsapp") or osm_tags.get("whatsapp")
    if whatsapp:
        digits = re.sub(r"[^\d+]", "", whatsapp)
        if digits:
            links.append(("WhatsApp", f"https://wa.me/{digits.lstrip('+')}"))

    facebook = osm_tags.get("contact:facebook") or osm_tags.get("facebook")
    if facebook:
        links.append(("Facebook", _social_url(facebook, "https://facebook.com/")))

    instagram = osm_tags.get("contact:instagram") or osm_tags.get("instagram")
    if instagram:
        links.append(("Instagram", _social_url(instagram.lstrip("@"), "https://instagram.com/")))

    telegram = osm_tags.get("contact:telegram") or osm_tags.get("telegram")
    if telegram:
        links.append(("Telegram", _social_url(telegram.lstrip("@"), "https://t.me/")))

    tiktok = osm_tags.get("contact:tiktok") or osm_tags.get("tiktok")
    if tiktok:
        links.append(("TikTok", _social_url(f"@{tiktok.lstrip('@')}", "https://tiktok.com/")))

    twitter = osm_tags.get("contact:twitter") or osm_tags.get("twitter") or osm_tags.get("contact:x")
    if twitter:
        links.append(("X", _social_url(twitter.lstrip("@"), "https://x.com/")))

    youtube = osm_tags.get("contact:youtube") or osm_tags.get("youtube")
    if youtube:
        links.append(("YouTube", _social_url(youtube, "https://youtube.com/")))

    return links


def _social_url(value: str, base: str) -> str:
    value = value.strip()
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return base + value.lstrip("/")


def _category_from_tags(tags: dict, industry: str) -> str:
    mapped = set(industry_tags(industry))
    osm_pairs = [(key, tags[key]) for key in _COMMERCIAL_KEYS if tags.get(key)]
    if mapped and any(pair in mapped for pair in osm_pairs):
        return industry
    if osm_pairs:
        return osm_pairs[0][1].replace("_", " ")
    return industry


def _from_osm(element: dict, industry: str) -> DiscoveryCandidate | None:
    tags = element.get("tags") or {}
    name = tags.get("name")
    if not name:
        return None
    website = tags.get("website") or tags.get("contact:website") or tags.get("url")
    osm_type = element.get("type", "node")
    osm_id = element.get("id")
    coords = element_coords(element)
    return DiscoveryCandidate(
        name=name,
        category=_category_from_tags(tags, industry),
        city=tags.get("addr:city") or tags.get("addr:town") or tags.get("addr:village"),
        region=tags.get("addr:province") or tags.get("addr:state"),
        country=tags.get("addr:country") or "IT",
        latitude=coords[0] if coords else None,
        longitude=coords[1] if coords else None,
        website_url=website,
        phone=_phone_from_tags(tags),
        email=tags.get("email") or tags.get("contact:email"),
        source="openstreetmap",
        external_id=f"{osm_type}/{osm_id}" if osm_id is not None else None,
        extra=_osm_extra(tags),
    )


def _from_nominatim(item: dict, industry: str) -> DiscoveryCandidate | None:
    name = item.get("name") or (item.get("display_name") or "").split(",")[0].strip()
    if not name:
        return None
    address = item.get("address") or {}
    extra = item.get("extratags") or {}
    osm_type = item.get("osm_type")
    osm_id = item.get("osm_id")
    coords = element_coords(item)
    class_key = item.get("class")
    class_value = item.get("type")
    tags = dict(extra)
    if isinstance(class_key, str) and isinstance(class_value, str):
        tags[class_key] = class_value
    return DiscoveryCandidate(
        name=name,
        category=_category_from_tags(tags, industry),
        city=address.get("city") or address.get("town") or address.get("village"),
        region=address.get("state") or address.get("province"),
        country=address.get("country_code", "it").upper() if address.get("country_code") else "IT",
        latitude=coords[0] if coords else None,
        longitude=coords[1] if coords else None,
        website_url=extra.get("website") or extra.get("contact:website") or extra.get("url"),
        phone=_phone_from_tags(extra),
        email=extra.get("email") or extra.get("contact:email"),
        source="openstreetmap",
        external_id=f"{osm_type}/{osm_id}" if osm_type and osm_id is not None else None,
        extra=_osm_extra(extra),
    )
