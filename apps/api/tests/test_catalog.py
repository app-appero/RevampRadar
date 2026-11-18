"""Catalogo settori della Discovery: ogni settore deve tradursi in almeno un tag OSM."""

import re

import pytest

from app.discovery.osm import (
    _COMMERCIAL_KEYS,
    _INDUSTRY_TAGS,
    format_industry_tags,
    industry_tags,
    listed_sectors,
    preview_industry,
)

_TAG_VALUE = re.compile(r"^[a-z][a-z0-9_]*$")


@pytest.mark.parametrize("sector", listed_sectors())
def test_every_catalog_sector_has_osm_tags(sector: str) -> None:
    tags = industry_tags(sector)
    assert tags, f"Il settore «{sector}» del catalogo non ha tag OSM"
    for key, value in tags:
        # Una chiave fuori da _COMMERCIAL_KEYS non finisce in osm_tags e scarterebbe ogni risultato.
        assert key in _COMMERCIAL_KEYS, f"«{sector}»: chiave {key} non conservata nei risultati"
        assert _TAG_VALUE.match(value), f"«{sector}»: valore OSM non valido {value!r}"
    assert format_industry_tags(sector)
    assert preview_industry(sector)["mapped"] is True


def test_catalog_api_lists_only_tagged_sectors(client) -> None:
    sectors = client.get("/discovery/catalog").json()["sectors"]
    assert sectors
    untagged = [sector for sector in sectors if not industry_tags(sector)]
    assert untagged == []


@pytest.mark.parametrize("name", sorted(_INDUSTRY_TAGS))
def test_every_alias_resolves_to_its_own_tags(name: str) -> None:
    # Protegge da normalizzazioni che renderebbero irraggiungibile una voce (es. "b&b").
    assert industry_tags(name) == _INDUSTRY_TAGS[name]


@pytest.mark.parametrize(
    ("sector", "expected"),
    [
        ("tappezziere", ("craft", "upholsterer")),
        ("fiorista", ("shop", "florist")),
        ("vivaio", ("shop", "garden_centre")),
        ("ferramenta", ("shop", "hardware")),
        ("cornici", ("shop", "frame")),
        ("sartoria", ("craft", "tailor")),
        ("calzolaio", ("craft", "shoemaker")),
        ("erboristeria", ("shop", "herbalist")),
    ],
)
def test_requested_sector_links(sector: str, expected: tuple[str, str]) -> None:
    assert expected in industry_tags(sector)
    # Il settore (o un sinonimo con gli stessi tag) è selezionabile dal menu del catalogo.
    assert any(industry_tags(item) == industry_tags(sector) for item in listed_sectors())
