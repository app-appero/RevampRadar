from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiscoveryQuery:
    industry: str
    location: str
    max_results: int


@dataclass
class DiscoveryCandidate:
    name: str
    category: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    website_url: str | None = None
    phone: str | None = None
    email: str | None = None
    source: str = "unknown"
    external_id: str | None = None
    extra: dict | None = None
