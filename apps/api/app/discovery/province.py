"""Ricerca per provincia: località per Nominatim e filtro deterministico dei risultati.

Una provincia (es. "BG" o "Bergamo") diventa la località "Provincia di Bergamo, Lombardia",
mai la sola sigla. I candidati trovati vengono poi tenuti solo se cadono nella provincia:
prima il poligono del confine (se Nominatim lo ha restituito), poi `addr:province`, poi
l'elenco dei comuni. Nessuna dipendenza esterna: il punto-nel-poligono è un ray casting.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, replace
from functools import lru_cache

from app.discovery.italy_geo import italy_geo
from app.discovery.types import DiscoveryCandidate

_PREFIX = re.compile(
    r"^(?:provincia(?:\s+autonoma)?|prov\.?|citt[aà]\s+metropolitana|libero\s+consorzio(?:\s+comunale)?)"
    r"\s+(?:di\s+|del\s+|della\s+|dell'\s*)?",
    re.IGNORECASE,
)
_CODE = re.compile(r"^[A-Za-z]{2}$")


def fold(value: str | None) -> str:
    """Confronto robusto tra nomi: senza accenti, minuscolo, apostrofi e spazi uniformi."""
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.replace("’", "'").replace("`", "'").casefold()
    return " ".join(text.split())


def _display(name: str) -> str:
    # "Bolzano/Bozen" → "Bolzano", "Trentino-Alto Adige/Südtirol" → "Trentino-Alto Adige".
    return name.split("/")[0].strip()


@dataclass(frozen=True)
class ProvinceScope:
    name: str
    code: str
    region: str
    cities: frozenset[str]

    @property
    def display_name(self) -> str:
        return _display(self.name)

    @property
    def region_display(self) -> str:
        return _display(self.region)

    @property
    def is_region(self) -> bool:
        """Valle d'Aosta: provincia e regione coincidono, si cerca la regione."""
        return fold(self.display_name) == fold(self.region_display)

    @property
    def location(self) -> str:
        if self.is_region:
            return self.region_display
        return f"Provincia di {self.display_name}, {self.region_display}"

    def matches_province_value(self, value: str | None) -> bool | None:
        """True/False se `value` è una provincia nota (sigla o nome), None se non lo è."""
        other = lookup_province(value or "")
        if other is None:
            return None
        return other.code == self.code


@lru_cache(maxsize=1)
def _index() -> tuple[dict[str, ProvinceScope], dict[str, set[str]]]:
    provinces: dict[str, ProvinceScope] = {}
    city_provinces: dict[str, set[str]] = {}
    for region in italy_geo().get("regions") or []:
        for item in region.get("provinces") or []:
            cities = frozenset(fold(city) for city in item.get("cities") or [])
            scope = ProvinceScope(
                name=item["name"],
                code=str(item.get("code") or "").upper(),
                region=region["name"],
                cities=cities,
            )
            keys = {fold(item["name"]), fold(scope.display_name), *(fold(part) for part in item["name"].split("/"))}
            if scope.code:
                keys.add(fold(scope.code))
            for key in keys:
                provinces.setdefault(key, scope)
            for city in cities:
                city_provinces.setdefault(city, set()).add(scope.code)
    return provinces, city_provinces


def lookup_province(value: str) -> ProvinceScope | None:
    """Accetta sigla ("BG"), nome ("Bergamo") o forma estesa ("Provincia di Bergamo")."""
    text = (value or "").strip()
    if not text:
        return None
    text = _PREFIX.sub("", text).strip()
    return _index()[0].get(fold(text))


def compose_location(*, region: str = "", province: str = "", city: str = "", location: str = "") -> str:
    """Località da inviare a Nominatim per una nuova discovery.

    - provincia senza città → "Provincia di Bergamo, Lombardia" (anche se arriva la sigla "BG");
    - città → "Zanica, Bergamo, Lombardia" (sigla tradotta nel nome);
    - solo regione → "Lombardia"; nulla → la località libera (sigle tradotte) o "Italia".
    Solleva ValueError se la provincia non è riconosciuta: meglio un errore che cercare altrove.
    """
    region = region.strip()
    province = province.strip()
    city = city.strip()
    scope = None
    if province:
        scope = lookup_province(province)
        if scope is None:
            raise ValueError(
                f"Provincia non riconosciuta: «{province}». Usa la sigla (es. BG) o il nome (es. Bergamo)."
            )
        region = scope.region_display
    elif region:
        region = _display(region)
    if city:
        parts = [city]
        if scope is not None and not scope.is_region:
            parts.append(scope.display_name)
        if region:
            parts.append(region)
        return ", ".join(parts)
    if scope is not None:
        return scope.location
    if region:
        return region
    return normalize_free_location(location) or "Italia"


def normalize_free_location(location: str) -> str:
    """Traduce le sigle di provincia in una località libera ("BG, Lombardia" → "Provincia di Bergamo, Lombardia")."""
    parts = [part.strip() for part in (location or "").split(",") if part.strip()]
    if not parts:
        return ""
    head = lookup_province(parts[0]) if _CODE.match(parts[0]) else None
    if head is not None:
        return head.location
    out: list[str] = []
    for part in parts:
        scope = lookup_province(part) if _CODE.match(part) else None
        out.append(scope.display_name if scope is not None else part)
    return ", ".join(out)


def province_scope_for_location(location: str) -> ProvinceScope | None:
    """Ambito provinciale di una località già composta, None per città/regione/Italia."""
    parts = [part.strip() for part in (location or "").split(",") if part.strip()]
    if not parts:
        return None
    first = parts[0]
    if _PREFIX.match(first) or _CODE.match(first):
        scope = lookup_province(first)
        if scope is not None and not scope.is_region:
            return scope
    return None


# --- filtro dei risultati -------------------------------------------------------------


def point_in_geojson(lat: float, lon: float, geometry: dict | None) -> bool | None:
    """Ray casting su Polygon/MultiPolygon GeoJSON (lon, lat). None se la geometria non è un'area."""
    if not isinstance(geometry, dict):
        return None
    kind = geometry.get("type")
    coords = geometry.get("coordinates")
    if kind == "Polygon":
        polygons = [coords]
    elif kind == "MultiPolygon":
        polygons = coords
    else:
        return None
    if not polygons:
        return None
    for rings in polygons:
        if not rings:
            continue
        outer, *holes = rings
        if _in_ring(lon, lat, outer) and not any(_in_ring(lon, lat, hole) for hole in holes):
            return True
    return False


def _in_ring(x: float, y: float, ring: list) -> bool:
    inside = False
    count = len(ring)
    if count < 3:
        return False
    j = count - 1
    for i in range(count):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def candidate_in_province(
    candidate: DiscoveryCandidate, scope: ProvinceScope, boundary: dict | None = None
) -> bool:
    if candidate.latitude is not None and candidate.longitude is not None and boundary is not None:
        inside = point_in_geojson(candidate.latitude, candidate.longitude, boundary)
        if inside is not None:
            return inside
    tags = (candidate.extra or {}).get("osm_tags") or {}
    for value in (tags.get("addr:province"), candidate.region):
        verdict = scope.matches_province_value(value)
        if verdict is not None:
            return verdict
    city = fold(candidate.city)
    if city:
        if city in scope.cities:
            return True
        if city in _index()[1]:
            return False  # comune noto di un'altra provincia (es. Brescia per Bergamo)
    # Né coordinate nel confine né indirizzo: resta, la query Overpass era già limitata all'area.
    return True


def filter_by_province(
    candidates: list[DiscoveryCandidate], scope: ProvinceScope, boundary: dict | None = None
) -> list[DiscoveryCandidate]:
    kept: list[DiscoveryCandidate] = []
    for candidate in candidates:
        if not candidate_in_province(candidate, scope, boundary):
            continue
        extra = dict(candidate.extra or {})
        extra.setdefault("province", scope.display_name)
        kept.append(replace(candidate, region=candidate.region or scope.region_display, extra=extra))
    return kept
