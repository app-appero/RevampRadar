from __future__ import annotations

from typing import Protocol

from app.config import Settings
from app.discovery.types import DiscoveryCandidate, DiscoveryQuery


class DiscoveryProvider(Protocol):
    name: str

    def search_businesses(self, query: DiscoveryQuery) -> list[DiscoveryCandidate]:
        """Return raw candidates. Must not persist anything."""


def get_discovery_provider(settings: Settings) -> DiscoveryProvider:
    from app.discovery.osm import OpenStreetMapProvider

    return OpenStreetMapProvider(settings)
