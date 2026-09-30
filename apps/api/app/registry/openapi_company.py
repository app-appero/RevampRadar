from __future__ import annotations

import re
from typing import Any

import httpx

from app.config import Settings


class RegistryError(Exception):
    """Errore del provider anagrafico. Il messaggio non contiene mai il token."""


def _get(path: str, settings: Settings, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    if not settings.openapi_company_token:
        raise RegistryError("openapi_company_token_missing")
    url = f"{settings.openapi_company_base_url.rstrip('/')}/{path.lstrip('/')}"
    try:
        response = httpx.get(
            url,
            params=params,
            headers={"Authorization": f"Bearer {settings.openapi_company_token}"},
            timeout=settings.openapi_company_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise RegistryError(f"openapi_company_network_{type(exc).__name__}") from None
    if response.status_code in (204, 404):  # nessun risultato
        return []
    if response.status_code != 200:
        raise RegistryError(f"openapi_company_http_{response.status_code}")
    data = response.json().get("data")
    return data if isinstance(data, list) else []


def _latest_balance(balance_sheets: dict[str, Any] | None) -> dict[str, Any]:
    entries = (balance_sheets or {}).get("all") or []
    with_turnover = [b for b in entries if b.get("turnover") is not None]
    return (with_turnover or entries or [{}])[0]


def normalize_company(raw: dict[str, Any]) -> dict[str, Any]:
    office = (raw.get("address") or {}).get("registeredOffice") or {}
    ateco = ((raw.get("atecoClassification") or {}).get("ateco2022")) or {}
    balance = _latest_balance(raw.get("balanceSheets"))
    return {
        "company_name": raw.get("companyName"),
        "vat_code": raw.get("vatCode"),
        "tax_code": raw.get("taxCode"),
        "activity_status": raw.get("activityStatus"),
        "legal_form": (raw.get("detailedLegalForm") or {}).get("description"),
        "pec": raw.get("pec"),
        "ateco_code": ateco.get("code"),
        "ateco_description": ateco.get("description"),
        "address": office.get("streetName"),
        "city": office.get("town"),
        "province": office.get("province"),
        "zip_code": office.get("zipCode"),
        "region": (office.get("region") or {}).get("description"),
        "start_date": raw.get("startDate"),
        "revenues": [
            {"year": b.get("year"), "turnover": b.get("turnover")}
            for b in (raw.get("balanceSheets") or {}).get("all") or []
            if b.get("turnover") is not None and b.get("year")
        ],
        "balance_year": balance.get("year"),
        "turnover": balance.get("turnover"),
        "employees": balance.get("employees"),
        "net_worth": balance.get("netWorth"),
    }


def lookup_by_vat(vat: str, settings: Settings) -> dict[str, Any] | None:
    rows = _get(f"IT-advanced/{vat.strip()}", settings)
    return normalize_company(rows[0]) if rows else None


def lookup_by_name(name: str, settings: Settings) -> dict[str, Any] | None:
    """IT-search restituisce solo gli id: il primo viene risolto con IT-advanced."""
    hits = _get("IT-search", settings, {"companyName": name.strip(), "limit": 1})
    if not hits or not hits[0].get("id"):
        return None
    rows = _get(f"IT-advanced/{hits[0]['id']}", settings)
    return normalize_company(rows[0]) if rows else None


_STOPWORDS = {
    "srl",
    "spa",
    "snc",
    "sas",
    "sapa",
    "ss",
    "di",
    "da",
    "del",
    "della",
    "dei",
    "delle",
    "e",
    "il",
    "la",
    "lo",
    "le",
    "i",
    "the",
    "societa",
    "societa'",
    "azienda",
    "ditta",
    "impresa",
    "individuale",
    "cooperativa",
    "coop",
    "a",
    "r",
    "l",
    "s",
    "p",
    "c",
    "n",
}
_MIN_NAME_SCORE = 0.6
_MAX_CANDIDATES = 5


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOPWORDS and len(t) > 1}


def _name_score(wanted: str, found: str) -> float:
    wanted_tokens = _tokens(wanted)
    if not wanted_tokens:
        return 0.0
    return len(wanted_tokens & _tokens(found)) / len(wanted_tokens)


def find_company(name: str, city: str | None, settings: Settings) -> dict[str, Any] | None:
    """Cerca per nome e sceglie solo una corrispondenza affidabile (nome simile e stesso comune).

    IT-search restituisce solo gli id: ogni candidato è verificato con IT-start (anagrafica base)
    prima di spendere la chiamata completa. Nessuna corrispondenza affidabile -> None.
    """
    hits = _get("IT-search", settings, {"companyName": name.strip(), "limit": _MAX_CANDIDATES})
    best: tuple[float, str] | None = None
    for hit in hits[:_MAX_CANDIDATES]:
        if not hit.get("id"):
            continue
        rows = _get(f"IT-start/{hit['id']}", settings)
        if not rows:
            continue
        candidate = rows[0]
        town = (((candidate.get("address") or {}).get("registeredOffice")) or {}).get("town") or ""
        if city and town.strip().lower() != city.strip().lower():
            continue
        score = _name_score(name, candidate.get("companyName") or "")
        if score >= _MIN_NAME_SCORE and (best is None or score > best[0]):
            best = (score, candidate.get("vatCode") or hit["id"])
    return lookup_by_vat(best[1], settings) if best else None
