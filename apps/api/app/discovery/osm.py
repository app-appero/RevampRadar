from __future__ import annotations

import re
import threading
import time
from collections import deque
from collections.abc import Callable
from urllib.parse import urlparse

import httpx

from app.config import Settings
from app.discovery.province import ProvinceScope, filter_by_province, fold, province_scope_for_location
from app.discovery.types import DiscoveryCandidate, DiscoveryQuery

StageCallback = Callable[..., None]

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
    # Mestieri e negozi aggiunti: ogni voce deve avere almeno un tag OSM (vedi test_catalog).
    "tappezziere": [("craft", "upholsterer")],
    "tappezzeria": [("craft", "upholsterer")],
    "vivaio": [("shop", "garden_centre")],
    "garden center": [("shop", "garden_centre")],
    "cornici": [("shop", "frame")],
    "corniciaio": [("shop", "frame")],
    "corniceria": [("shop", "frame")],
    "sartoria": [("craft", "tailor"), ("shop", "tailor")],
    "sarto": [("craft", "tailor"), ("shop", "tailor")],
    "calzolaio": [("craft", "shoemaker"), ("shop", "shoe_repair")],
    "orologeria": [("shop", "watches"), ("craft", "watchmaker")],
    "orologiaio": [("shop", "watches"), ("craft", "watchmaker")],
    "orafo": [("craft", "jeweller"), ("shop", "jewelry")],
    "vetreria": [("craft", "glaziery")],
    "vetraio": [("craft", "glaziery")],
    "merceria": [("shop", "sewing"), ("shop", "fabric")],
    "tessuti": [("shop", "fabric")],
    "profumeria": [("shop", "perfumery")],
    "erboristeria": [("shop", "herbalist")],
    "materassi": [("shop", "bed")],
    "tende": [("shop", "curtain")],
    "illuminazione": [("shop", "lighting")],
    "colorificio": [("shop", "paint")],
    "piastrelle": [("shop", "tiles")],
    "elettrodomestici": [("shop", "appliance")],
    "casalinghi": [("shop", "houseware")],
    "articoli da regalo": [("shop", "gift")],
    "antiquario": [("shop", "antiques")],
    "biciclette": [("shop", "bicycle")],
    "ciclista": [("shop", "bicycle")],
    "moto": [("shop", "motorcycle")],
    "fruttivendolo": [("shop", "greengrocer")],
    "ortofrutta": [("shop", "greengrocer")],
    "formaggi": [("shop", "cheese")],
    "cioccolateria": [("shop", "chocolate")],
    "torrefazione": [("shop", "coffee")],
    "birrificio": [("craft", "brewery")],
    "cantina": [("craft", "winery")],
    "strumenti musicali": [("shop", "musical_instrument")],
    "liutaio": [("craft", "luthier")],
    "sanitaria": [("shop", "medical_supply")],
    "toelettatura": [("shop", "pet_grooming")],
    "serramenti": [("craft", "window_construction")],
    "infissi": [("craft", "window_construction")],
    "marmista": [("craft", "stonemason")],
    "giardiniere": [("craft", "gardener")],
    "climatizzazione": [("craft", "hvac")],
    "insegne": [("craft", "signmaker")],
    "ceramiche": [("craft", "pottery")],
    "apicoltore": [("craft", "beekeeper")],
    "podologo": [("healthcare", "podiatrist")],
    "logopedista": [("healthcare", "speech_therapist")],
    "nutrizionista": [("healthcare", "nutrition_counselling")],
    "autonoleggio": [("amenity", "car_rental")],
    "traslochi": [("office", "moving_company")],
    "maneggio": [("leisure", "horse_riding")],
    "casa vacanze": [("tourism", "apartment")],
    "scuola di danza": [("amenity", "dancing_school")],
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
# Ordine di prova. I server di riserva (kumi.systems, private.coffee) stanno su reti diverse da
# overpass-api.de: se quello principale non è raggiungibile, lz4 (stessa infrastruttura) di solito
# non lo è nemmeno, quindi va per ultimo.
_DEFAULT_OVERPASS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
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


class OverpassTimeoutError(RuntimeError):
    """Overpass non ha completato la query in tempo (timeout HTTP, 504 o remark di timeout)."""


class OverpassUnavailableError(RuntimeError):
    """Nessun server Overpass raggiungibile: errori di rete (es. Errno 101) su tutti gli endpoint."""


class OverpassBusyError(RuntimeError):
    """Server Overpass sovraccarichi (429/502/503): transitorio, si riprova dopo un'attesa."""


_BUSY_STATUSES = frozenset({429, 502, 503})
_SLOTS_LOCK = threading.Lock()
_SLOTS: dict[int, threading.BoundedSemaphore] = {}


def _overpass_slots(size: int) -> threading.BoundedSemaphore:
    """Semaforo di processo: limita le richieste Overpass contemporanee di tutte le discovery."""
    size = max(1, int(size))
    with _SLOTS_LOCK:
        if size not in _SLOTS:
            _SLOTS[size] = threading.BoundedSemaphore(size)
        return _SLOTS[size]


def _host(url: str) -> str:
    return urlparse(url).hostname or url


def _network_reason(exc: BaseException) -> str:
    text = " ".join(str(exc).split()) or exc.__class__.__name__
    return text[:160]


_AREA_TIMEOUT_MESSAGE = (
    "La ricerca su un'area così ampia non è riuscita a completarsi nel tempo "
    "disponibile su Overpass (non è detto che non ci siano risultati). Riprova, "
    "oppure restringi a provincia/città o a un settore specifico."
)
_RELATION_AREA_OFFSET = 3600000000


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
        # Ultimo server Overpass che ha risposto: le query successive della stessa ricerca
        # (es. i gruppi di comuni) partono da lì invece di riprovare un server irraggiungibile.
        self._preferred_overpass: str | None = None
        # Server irraggiungibili in questa ricerca: provati per ultimi e saltati quando servirebbero
        # solo a confermare un risultato vuoto.
        self._unreachable_overpass: set[str] = set()

    def _overpass_order(self) -> list[str]:
        endpoints = overpass_endpoints(self._settings)
        reachable = [url for url in endpoints if url not in self._unreachable_overpass]
        down = [url for url in endpoints if url in self._unreachable_overpass]
        ordered = reachable + down
        if self._preferred_overpass in ordered:
            ordered.remove(self._preferred_overpass)
            ordered.insert(0, self._preferred_overpass)
        return ordered

    def search_businesses(
        self,
        query: DiscoveryQuery,
        on_stage: StageCallback | None = None,
    ) -> list[DiscoveryCandidate]:
        self.last_warning: str | None = None
        tags = resolve_search_tags(query.industry)
        if not tags:
            return []
        stage: StageCallback = on_stage or (lambda *_args, **_kwargs: None)
        scope = province_scope_for_location(query.location)
        stage("Ricerca località")
        area = self._resolve_province_area(scope) if scope else self._resolve_area(query.location)
        fetch_limit = min(400, max(query.max_results * 2, 25))
        elements: list[dict] = []
        overpass_error: RuntimeError | None = None
        stage("Query Overpass")
        # In provincia si interroga l'area del confine, non il rettangolo (bbox) che sconfina
        # nelle province vicine (es. Bergamo → Brescia).
        province_area = bool(scope and area.get("area_id"))
        search_area = {"area_id": area["area_id"]} if province_area else area
        # Errori transitori (rete, server sovraccarichi; su città e regioni anche il timeout):
        # stessa query ripetuta con attesa crescente. In provincia il timeout passa invece alla
        # ricerca per comuni, che ha i suoi tentativi per gruppo.
        transient: tuple[type[RuntimeError], ...] = (OverpassUnavailableError, OverpassBusyError)
        if not province_area:
            transient = (*transient, OverpassTimeoutError)
        try:
            elements = self._with_retry(
                lambda: self._overpass(search_area, tags, fetch_limit),
                retry_on=transient,
                on_retry=lambda attempt, attempts: stage(
                    f"Overpass non disponibile · nuovo tentativo {attempt}/{attempts}"
                ),
            )
        except OverpassTimeoutError as exc:
            if province_area and scope is not None:
                elements = self._overpass_by_comuni(area, scope, tags, fetch_limit, stage)
            else:
                overpass_error = exc
        except RuntimeError as exc:
            overpass_error = exc
        matched: list[DiscoveryCandidate] = []
        for item in elements:
            candidate = _from_osm(item, query.industry)
            if candidate is not None and candidate_matches_industry(candidate, query.industry):
                matched.append(candidate)
        if scope is not None:
            matched = filter_by_province(matched, scope, area.get("boundary"))
        found = select_candidates(matched, query)
        if found:
            return found
        if overpass_error is not None:
            raise overpass_error
        return []

    def _nominatim_get(self, params: dict) -> list[dict]:
        url = self._settings.nominatim_url.rstrip("/") + "/search"
        headers = {"User-Agent": self._settings.scanner_user_agent, "Accept": "application/json"}
        timeout = httpx.Timeout(self._settings.discovery_timeout_seconds)
        try:
            with httpx.Client(timeout=timeout, headers=headers) as client:
                response = client.get(url, params=params)
        except (httpx.TransportError, OSError) as exc:
            raise RuntimeError(f"Nominatim non raggiungibile ({_network_reason(exc)}). Riprova più tardi.") from exc
        if response.status_code >= 400:
            raise RuntimeError(f"Nominatim HTTP {response.status_code}")
        payload = response.json()
        return payload if isinstance(payload, list) else []

    def _resolve_area(self, location: str) -> dict:
        payload = self._nominatim_get({"q": location, "format": "json", "limit": 1, "addressdetails": 1})
        if not payload:
            raise RuntimeError(f"Località non trovata: {location}")
        return _area_from_nominatim(payload[0])

    def _resolve_province_area(self, scope: ProvinceScope) -> dict:
        """Confine amministrativo della provincia (admin_level 6), con poligono semplificato."""
        base = {
            "format": "json",
            "addressdetails": 1,
            "limit": 5,
            "countrycodes": "it",
            "polygon_geojson": 1,
            "polygon_threshold": 0.001,
        }
        attempts = (
            {"q": scope.location},
            # Città metropolitane e province rinominate: ricerca strutturata per "county".
            {"county": scope.display_name, "state": scope.region_display, "country": "Italia"},
        )
        fallback: dict | None = None
        for index, params in enumerate(attempts):
            if index:
                time.sleep(1.05)  # Nominatim ammette ~1 richiesta al secondo.
            payload = self._nominatim_get({**base, **params})
            if fallback is None and payload:
                fallback = payload[0]
            pick = next((item for item in payload if _is_province_boundary(item)), None)
            if pick is not None:
                return _area_from_nominatim(pick, with_boundary=True)
        if fallback is None:
            raise RuntimeError(f"Località non trovata: {scope.location}")
        # Nessun confine provinciale riconosciuto: si filtra comunque per comuni/indirizzo.
        return _area_from_nominatim(fallback)

    def _overpass(
        self,
        area: dict,
        tags: list[tuple[str, str]],
        limit: int,
        *,
        name_regex: str | None = None,
    ) -> list[dict]:
        # Prima era fissato a min(25, ...): su un'area grande (regione, "tutti i settori") Overpass
        # spesso non fa in tempo e risponde con un "remark" di timeout ed elements vuoto, che veniva
        # interpretato come "zero risultati" invece che come ricerca non completata. Ora si rispetta
        # il timeout configurato (fino a un tetto ragionevole per un uso interattivo) e si distingue
        # il timeout server-side da uno zero risultati genuino.
        timeout_s = self._overpass_timeout()
        query = _build_overpass_query(area, tags, limit, timeout_s, name_regex=name_regex)
        return self._post_overpass(query, timeout_s)

    def _slot(self):
        return _overpass_slots(self._settings.overpass_max_concurrency)

    def _overpass_timeout(self) -> int:
        return min(55, max(20, int(self._settings.discovery_timeout_seconds)))

    def _post_overpass(self, query: str, timeout_s: int) -> list[dict]:
        """Prova i server Overpass in ordine; passa al successivo su rete, timeout o errore HTTP."""
        last_error: RuntimeError | None = None
        empty_ok = False
        timed_out = False
        unreachable: list[str] = []
        network_reason = ""
        http_timeout = httpx.Timeout(connect=10.0, read=float(timeout_s + 15), write=10.0, pool=10.0)
        headers = {"User-Agent": self._settings.scanner_user_agent}
        endpoints = self._overpass_order()
        first_answer: str | None = None
        for url in endpoints:
            if empty_ok and url in self._unreachable_overpass:
                continue
            try:
                with self._slot(), httpx.Client(timeout=http_timeout, headers=headers) as client:
                    response = client.post(url, data={"data": query})
            except httpx.ConnectTimeout as exc:
                unreachable.append(_host(url))
                self._unreachable_overpass.add(url)
                network_reason = _network_reason(exc) or "connessione scaduta"
                continue
            except httpx.TimeoutException:
                timed_out = True
                last_error = OverpassTimeoutError(overpass_error_message(504, "timeout"))
                continue
            except (httpx.TransportError, OSError) as exc:
                # Es. "[Errno 101] Network is unreachable": prima interrompeva tutta la ricerca
                # senza provare i server di riserva.
                unreachable.append(_host(url))
                self._unreachable_overpass.add(url)
                network_reason = _network_reason(exc)
                continue
            self._unreachable_overpass.discard(url)
            if response.status_code >= 400:
                timed_out = timed_out or response.status_code == 504
                error_type = OverpassBusyError if response.status_code in _BUSY_STATUSES else RuntimeError
                last_error = error_type(overpass_error_message(response.status_code, response.text))
                continue
            try:
                payload = response.json()
            except ValueError:
                last_error = RuntimeError(overpass_error_message(response.status_code, response.text))
                continue
            elements = payload.get("elements") or []
            if elements:
                self._preferred_overpass = url
                return elements
            remark = str(payload.get("remark") or "").lower()
            if "timed out" in remark or "timeout" in remark:
                timed_out = True
                last_error = OverpassTimeoutError(_AREA_TIMEOUT_MESSAGE)
                continue
            # Zero risultati: si chiede conferma agli altri server raggiungibili (un mirror può
            # non avere ancora l'area), ma il preferito resta il primo che ha risposto.
            first_answer = first_answer or url
            empty_ok = True
        if empty_ok:
            self._preferred_overpass = first_answer
            return []
        if last_error is not None:
            if timed_out and not isinstance(last_error, OverpassTimeoutError):
                raise OverpassTimeoutError(str(last_error))
            raise last_error
        if unreachable:
            raise OverpassUnavailableError(
                f"Overpass non raggiungibile: errore di rete su tutti i {len(endpoints)} server provati "
                f"({', '.join(unreachable)}; ultimo errore: {network_reason}). "
                "Riprova più tardi con «Riprova ricerca» (POST /discoveries/{id}/retry)."
            )
        return []

    def _with_retry(
        self,
        run: Callable[[], list[dict]],
        on_retry: Callable[[int, int], None] | None = None,
        *,
        retry_on: tuple[type[RuntimeError], ...] = (RuntimeError,),
    ):
        """Ripete una query Overpass fallita con attesa crescente (2s, 4s, ...)."""
        attempts = max(1, int(self._settings.overpass_retry_attempts))
        backoff = max(0.0, float(self._settings.overpass_retry_backoff_seconds))
        last: RuntimeError | None = None
        for attempt in range(1, attempts + 1):
            try:
                return run()
            except retry_on as exc:
                last = exc
                if attempt < attempts:
                    if on_retry:
                        on_retry(attempt + 1, attempts)
                    time.sleep(backoff * attempt)
        assert last is not None
        raise last

    def _province_comuni(self, area: dict, scope: ProvinceScope) -> list[tuple[int, str]]:
        """Comuni (admin_level 8) della provincia come (id relazione, nome)."""
        timeout_s = self._overpass_timeout()
        query = (
            f"[out:json][timeout:{timeout_s}];area({int(area['area_id'])})->.p;"
            'rel(area.p)["boundary"="administrative"]["admin_level"="8"];out tags;'
        )
        elements = self._with_retry(lambda: self._post_overpass(query, timeout_s))
        comuni: list[tuple[int, str]] = []
        for element in elements:
            tags = element.get("tags") or {}
            name = tags.get("name:it") or tags.get("name")
            if element.get("type") == "relation" and element.get("id") is not None and name:
                comuni.append((int(element["id"]), str(name)))
        # rel(area) include anche i comuni confinanti: si tengono quelli della provincia.
        own = [item for item in comuni if fold(item[1]) in scope.cities]
        return sorted(own or comuni, key=lambda item: fold(item[1]))

    def _overpass_by_comuni(
        self,
        area: dict,
        scope: ProvinceScope,
        tags: list[tuple[str, str]],
        limit: int,
        stage: StageCallback,
    ) -> list[dict]:
        """Overpass è andato in timeout sulla provincia: stessa ricerca per gruppi di comuni.

        Ogni gruppo viene ripetuto automaticamente; se continua a fallire si divide a metà,
        fino al singolo comune. I comuni rimasti senza risposta finiscono in `last_warning`
        (discovery "partial"); se non risponde nessun gruppo la ricerca fallisce.
        """
        try:
            comuni = self._province_comuni(area, scope)
        except OverpassUnavailableError:
            raise
        except RuntimeError as exc:
            raise OverpassTimeoutError(
                f"Overpass in timeout sulla provincia e impossibile elencarne i comuni: {exc}"
            ) from exc
        if not comuni:
            raise OverpassTimeoutError(_AREA_TIMEOUT_MESSAGE)
        size = max(1, int(self._settings.overpass_comuni_group_size))
        queue: deque[list[tuple[int, str]]] = deque(
            comuni[index : index + size] for index in range(0, len(comuni), size)
        )
        total = len(comuni)
        done = 0
        failed: list[str] = []
        found: dict[tuple[str, int], dict] = {}
        timeout_s = self._overpass_timeout()

        def report(suffix: str = "") -> None:
            percent = 40 + int(14 * done / total)
            stage(f"Overpass in timeout: ricerca per comuni {done}/{total}{suffix}", percent)

        report()
        while queue:
            group = queue.popleft()
            query = _build_overpass_query(
                {"area_ids": [_RELATION_AREA_OFFSET + rel_id for rel_id, _ in group]},
                tags,
                limit,
                timeout_s,
            )
            try:
                elements = self._with_retry(
                    lambda query=query: self._post_overpass(query, timeout_s),
                    on_retry=lambda attempt, attempts: report(f" · nuovo tentativo {attempt}/{attempts}"),
                )
            except OverpassUnavailableError as exc:
                # Rete giù anche dopo i tentativi: dividere il gruppo non servirebbe. Si chiude con
                # quello che è stato trovato e si indicano i comuni ancora da cercare.
                missing = len(group) + sum(len(item) for item in queue)
                if not found and done == 0:
                    raise
                self.last_warning = (
                    f"Ricerca per comuni interrotta: {done}/{total} comuni completati, {missing} da cercare. "
                    f"{exc}"
                )
                report(" · interrotta (rete)")
                return list(found.values())
            except RuntimeError:
                if len(group) > 1:
                    half = len(group) // 2
                    queue.appendleft(group[half:])
                    queue.appendleft(group[:half])
                    report(" · gruppo diviso")
                else:
                    failed.append(group[0][1])
                    done += 1
                    report(f" · {len(failed)} non completati")
                continue
            for element in elements:
                key = (str(element.get("type")), int(element.get("id") or 0))
                found.setdefault(key, element)
            done += len(group)
            report(f" · {len(failed)} non completati" if failed else "")
        if failed and len(failed) == total:
            raise OverpassTimeoutError(_AREA_TIMEOUT_MESSAGE)
        if failed:
            sample = ", ".join(failed[:5]) + ("…" if len(failed) > 5 else "")
            self.last_warning = (
                f"Ricerca per comuni: {total - len(failed)}/{total} comuni completati; "
                f"Overpass non ha risposto per {len(failed)} ({sample}). Rilancia per completarli."
            )
        return list(found.values())

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


def reverse_geocode(settings: Settings, latitude: float, longitude: float) -> dict[str, str | None] | None:
    """Chiede a Nominatim città/regione/paese per delle coordinate note.

    Usata su richiesta esplicita per una singola azienda (bottone "Recupera città"),
    non durante la discovery: Nominatim ammette ~1 richiesta/secondo, farlo per ogni
    azienda senza indirizzo in una ricerca estesa rallenterebbe troppo la ricerca.
    """
    url = settings.nominatim_url.rstrip("/") + "/reverse"
    headers = {"User-Agent": settings.scanner_user_agent, "Accept": "application/json"}
    timeout = httpx.Timeout(settings.discovery_timeout_seconds)
    with httpx.Client(timeout=timeout, headers=headers) as client:
        response = client.get(
            url,
            params={"lat": latitude, "lon": longitude, "format": "jsonv2", "addressdetails": 1, "zoom": 14},
        )
    if response.status_code >= 400:
        raise RuntimeError(f"Nominatim HTTP {response.status_code}")
    payload = response.json()
    if not isinstance(payload, dict):
        return None
    address = payload.get("address")
    if not isinstance(address, dict):
        return None
    city = address.get("city") or address.get("town") or address.get("village") or address.get("municipality")
    region = address.get("state") or address.get("province")
    country = address.get("country_code", "").upper() or None
    if not city and not region:
        return None
    return {"city": city, "region": region, "country": country}


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
    area_ids = area.get("area_ids")
    if area_ids:
        ids = ",".join(str(int(item)) for item in area_ids)
        parts = _overpass_filters(tags, name_regex, "(area.searchArea)")
        return (
            f"[out:json][timeout:{timeout}];"
            f"area(id:{ids})->.searchArea;({''.join(parts)});out center {limit};"
        )
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


def _area_from_nominatim(item: dict, *, with_boundary: bool = False) -> dict:
    osm_type = item.get("osm_type")
    osm_id = item.get("osm_id")
    if osm_type not in {"relation", "way", "node"} or not osm_id:
        raise RuntimeError("Nominatim non ha restituito un'area OSM valida.")
    prefix = {"relation": _RELATION_AREA_OFFSET, "way": 2400000000, "node": 0}[osm_type]
    geometry = item.get("geojson") if with_boundary else None
    is_area = isinstance(geometry, dict) and geometry.get("type") in {"Polygon", "MultiPolygon"}
    return {
        "area_id": prefix + int(osm_id) if prefix else None,
        "bbox": item.get("boundingbox"),
        "display_name": item.get("display_name"),
        "boundary": geometry if is_area else None,
    }


def _is_province_boundary(item: dict) -> bool:
    """Relazione amministrativa di livello provinciale (admin_level 6 → place_rank 12)."""
    if item.get("osm_type") != "relation":
        return False
    if (item.get("class") or item.get("category")) != "boundary":
        return False
    if item.get("addresstype") in {"county", "province"}:
        return True
    try:
        rank = int(item.get("place_rank") or 0)
    except (TypeError, ValueError):
        return False
    return 9 <= rank <= 13


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
