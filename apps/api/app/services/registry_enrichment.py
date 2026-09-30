"""Recupero dei dati aziendali (fatturato, dipendenti, forma giuridica, anno) dal Registro Imprese.

Usa OpenAPI.com Company e salva i risultati come Business Signals con fonte e affidabilità
`verified`. I segnali inseriti a mano non vengono mai sovrascritti.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import Settings
from app.models.entities import BusinessSignal, Company
from app.registry.openapi_company import RegistryError, find_company, lookup_by_vat
from app.services.ai_settings import effective_settings

SOURCE = "OpenAPI.com – Registro Imprese"
_MAX_REVENUE_YEARS = 3


class EnrichmentError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _signals(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    revenues = sorted(data.get("revenues") or [], key=lambda r: r["year"], reverse=True)
    for item in revenues[:_MAX_REVENUE_YEARS]:
        rows.append(
            {
                "key": "revenue",
                "period": str(item["year"]),
                "label": "Fatturato",
                "value": str(item["turnover"]),
                "unit": "EUR",
            }
        )
    if data.get("employees") is not None:
        period = str(data["balance_year"]) if data.get("balance_year") else ""
        rows.append(
            {"key": "employees", "period": period, "label": "Dipendenti", "value": str(data["employees"]), "unit": None}
        )
    if data.get("start_date"):
        rows.append(
            {
                "key": "founding_year",
                "period": "",
                "label": "Anno di fondazione",
                "value": str(data["start_date"])[:4],
                "unit": None,
            }
        )
    if data.get("legal_form"):
        rows.append(
            {"key": "legal_form", "period": "", "label": "Forma societaria", "value": data["legal_form"], "unit": None}
        )
    return rows


def enrich_from_registry(
    session: Session, company_id: UUID, base_settings: Settings, vat: str | None = None
) -> list[BusinessSignal]:
    company = session.get(Company, company_id)
    if company is None:
        raise EnrichmentError("Azienda non trovata.", status_code=404)
    settings = effective_settings(session, base_settings)
    if not settings.openapi_company_token:
        raise EnrichmentError("Token OpenAPI.com non configurato: aggiungilo in Impostazioni.", status_code=503)
    try:
        data = (
            lookup_by_vat(vat, settings) if vat and vat.strip() else find_company(company.name, company.city, settings)
        )
    except RegistryError as exc:
        raise EnrichmentError(f"Errore OpenAPI.com: {exc}", status_code=502) from None
    if data is None:
        raise EnrichmentError(
            "Nessuna corrispondenza affidabile nel Registro Imprese. Puoi indicare la P.IVA per cercarla direttamente.",
            status_code=404,
        )
    now = datetime.now(UTC)
    saved: list[BusinessSignal] = []
    for row in _signals(data):
        existing = (
            session.query(BusinessSignal)
            .filter_by(company_id=company_id, key=row["key"], period=row["period"])
            .one_or_none()
        )
        if existing is not None and existing.is_manual:
            continue
        if existing is None:
            existing = BusinessSignal(company_id=company_id, key=row["key"], period=row["period"])
            session.add(existing)
        existing.label = row["label"]
        existing.value = row["value"]
        existing.unit = row["unit"]
        existing.source = f"{SOURCE} ({data.get('company_name')}, P.IVA {data.get('vat_code')})"
        existing.observed_at = now
        existing.confidence = "verified"
        existing.is_manual = False
        saved.append(existing)
    session.commit()
    return saved
