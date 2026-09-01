from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_DATA = Path(__file__).with_name("data") / "italy_geo.json"


@lru_cache(maxsize=1)
def italy_geo() -> dict:
    return json.loads(_DATA.read_text(encoding="utf-8"))


def compose_location(region: str = "", province: str = "", city: str = "") -> str:
    parts = [item.strip() for item in (city, province, region) if item and item.strip()]
    return ", ".join(parts) if parts else "Italia"
