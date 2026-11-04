"""Export/import JSON della pipeline, pensato per l'arricchimento esterno (es. GPT).

L'export contiene tutto quello che l'app sa di ogni azienda (anagrafica, contatti,
social, stato CRM, tag, note, attività, punteggi, problemi del sito). L'import
aggiorna le aziende esistenti (chiave: ``company_id``) in modo non distruttivo:
valori vuoti/null non cancellano mai i dati già presenti.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from app.discovery.normalize import normalize_email, normalize_phone
from app.discovery.osm import social_contact_links
from app.discovery.service import DiscoveryServiceError, _clean_social_links, _link_website
from app.models.entities import (
    Activity,
    Audit,
    Company,
    Opportunity,
    OpportunityNote,
    OpportunityTag,
    Tag,
)
from app.scanner.url import UrlValidationError, normalize_url
from app.schemas.crm import CRM_STATUSES
from app.services.crm_service import (
    _normalize_tag,
    ensure_opportunity,
    latest_growth_scores_map,
    latest_scores_map,
    list_opportunities,
)

EXPORT_FORMAT = "revampradar.pipeline"
EXPORT_VERSION = 1
MAX_FINDINGS = 25
_EMAIL = re.compile(r"[^@\s]+@[^@\s.]+(?:\.[^@\s.]+)+")

GPT_INSTRUCTIONS = (
    "File esportato da RevampRadar. Per ogni azienda in 'companies' cerca informazioni aggiornate "
    "(sito web, social, Google Maps, directory) e restituisci LO STESSO JSON con i campi compilati. "
    "Mantieni invariati 'format', 'version' e 'company_id' (serve per reimportare). "
    "Campi modificabili: category, city, region, country, website_url, phone, email, "
    "social_links [{label,url}], status, is_favorite, tags [stringhe], new_notes [stringhe]. "
    "Gli altri campi (punteggi, audit, attivita, note esistenti) sono solo contesto e vengono ignorati. "
    "Non inventare dati: se non trovi un contatto lascia il campo com'e'. "
    "Se l'attivita risulta chiusa/cessata imposta status='uncontactable' e spiega nelle new_notes. "
    f"Valori validi per status: {', '.join(CRM_STATUSES)}."
)


class PipelineImportError(Exception):
    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _social_links(company: Company) -> list[dict[str, str]]:
    extra = company.extra or {}
    manual = extra.get("social_links")
    if isinstance(manual, list):
        return [
            {"label": str(item.get("label", "")), "url": str(item["url"])}
            for item in manual
            if isinstance(item, dict) and item.get("url")
        ]
    tags = extra.get("osm_tags") if isinstance(extra.get("osm_tags"), dict) else None
    return [{"label": label, "url": url} for label, url in social_contact_links(tags)]


def _latest_audit_findings(session: Session, audit_ids: list[UUID]) -> dict[UUID, Audit]:
    if not audit_ids:
        return {}
    audits = (
        session.query(Audit)
        .options(selectinload(Audit.findings))
        .filter(Audit.id.in_(audit_ids))
        .all()
    )
    return {audit.id: audit for audit in audits}


def build_export(session: Session, **filters: Any) -> dict[str, Any]:
    """Esporta le opportunità che rispettano i filtri della Pipeline."""
    opportunities = list_opportunities(session, **filters)
    ids = [item.id for item in opportunities]
    company_ids = [item.company_id for item in opportunities]
    scores = latest_scores_map(session, company_ids)
    growth = latest_growth_scores_map(session, company_ids)
    audits = _latest_audit_findings(session, [score.audit_id for score in scores.values()])
    # Note e attività vengono caricate in blocco per evitare una query per riga.
    full = {
        item.id: item
        for item in session.query(Opportunity)
        .options(selectinload(Opportunity.notes), selectinload(Opportunity.activities))
        .filter(Opportunity.id.in_(ids))
        .all()
    } if ids else {}

    companies: list[dict[str, Any]] = []
    for opportunity in opportunities:
        company = opportunity.company
        detail = full.get(opportunity.id, opportunity)
        website = company.websites[0] if company.websites else None
        score = scores.get(company.id)
        growth_score = growth.get(company.id)
        audit = audits.get(score.audit_id) if score else None
        basis = score or growth_score  # con sito: score audit; senza sito: growth score
        osm_tags = (company.extra or {}).get("osm_tags")
        companies.append(
            {
                "company_id": str(company.id),
                "name": company.name,
                "category": company.category,
                "city": company.city,
                "region": company.region,
                "country": company.country,
                "latitude": company.latitude,
                "longitude": company.longitude,
                "website_url": company.website_url or (website.normalized_url if website else None),
                "phone": company.phone,
                "email": company.email,
                "social_links": _social_links(company),
                "contacts_checked_at": _iso(company.places_checked_at),
                "source": company.source,
                "osm_tags": osm_tags if isinstance(osm_tags, dict) else {},
                "segment": "refactor" if (company.website_url or company.websites) else "greenfield",
                "status": opportunity.status,
                "is_favorite": opportunity.is_favorite,
                "tags": sorted(link.tag.name for link in opportunity.tag_links if link.tag is not None),
                "notes": [
                    {"body": note.body, "created_at": _iso(note.created_at)}
                    for note in sorted(detail.notes, key=lambda n: n.created_at)
                ],
                "activities": [
                    {
                        "type": act.type,
                        "note": act.note,
                        "occurred_at": _iso(act.occurred_at),
                        "due_at": _iso(act.due_at),
                        "completed_at": _iso(act.completed_at),
                    }
                    for act in sorted(detail.activities, key=lambda a: a.created_at)
                ],
                "scores": {
                    "website_score": score.website_score if score else None,
                    "business_score": score.business_score if score else None,
                    "opportunity_score": score.opportunity_score if score else None,
                    "priority": score.priority if score else None,
                    "growth_score": growth_score.score if growth_score else None,
                    "growth_priority": growth_score.priority if growth_score else None,
                    "recommended_service": getattr(basis, "recommended_service", None),
                    "explanation": getattr(basis, "explanation", None),
                    "top_reasons": getattr(basis, "top_reasons", []),
                    "negative_factors": getattr(basis, "negative_factors", []),
                },
                "audit_findings": [
                    {
                        "category": finding.category,
                        "severity": finding.severity,
                        "title": finding.title,
                        "description": finding.description,
                    }
                    for finding in (audit.findings[:MAX_FINDINGS] if audit else [])
                ],
                "new_notes": [],
            }
        )
    return {
        "format": EXPORT_FORMAT,
        "version": EXPORT_VERSION,
        "exported_at": datetime.now(UTC).isoformat(),
        "instructions": GPT_INSTRUCTIONS,
        "filters": {key: value for key, value in filters.items() if value not in (None, False, "")},
        "total": len(companies),
        "companies": companies,
    }


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _find_company(session: Session, item: dict[str, Any]) -> Company | None:
    raw_id = item.get("company_id")
    if isinstance(raw_id, str):
        try:
            company = session.get(Company, UUID(raw_id))
        except ValueError:
            company = None
        if company is not None:
            return company
    name, city = _text(item.get("name")), _text(item.get("city"))
    if not name:
        return None
    query = session.query(Company).filter(Company.name == name)
    if city:
        query = query.filter(Company.city == city)
    matches = query.limit(2).all()
    return matches[0] if len(matches) == 1 else None


def _apply_item(session: Session, company: Company, item: dict[str, Any]) -> list[str]:
    """Applica un elemento all'azienda; ritorna i campi cambiati. Solleva ValueError se non valido."""
    changed: list[str] = []

    for field, limit in (("category", 128), ("city", 128), ("region", 128), ("country", 64)):
        value = _text(item.get(field))
        if value and value[:limit] != getattr(company, field):
            setattr(company, field, value[:limit])
            changed.append(field)

    if item.get("website_url"):
        try:
            normalized = normalize_url(str(item["website_url"]))
        except UrlValidationError as exc:
            raise ValueError(f"website_url non valido: {item['website_url']}") from exc
        if normalized.normalized != company.website_url:
            company.website_url = normalized.normalized
            _link_website(session, company, normalized.normalized)
            changed.append("website_url")

    if item.get("phone"):
        phone = normalize_phone(str(item["phone"]))
        if phone and phone != company.phone:
            company.phone = phone[:64]
            changed.append("phone")

    if item.get("email"):
        email = normalize_email(str(item["email"]))
        if email is None or not _EMAIL.fullmatch(email):
            raise ValueError(f"email non valida: {item['email']}")
        if email != company.email:
            company.email = email
            changed.append("email")

    links = item.get("social_links")
    if isinstance(links, list) and links:
        incoming: list[tuple[str, str]] = []
        for link in links:
            if isinstance(link, dict) and link.get("url"):
                incoming.append((str(link.get("label") or ""), str(link["url"])))
            elif isinstance(link, str):
                incoming.append(("", link))
        existing = [(entry["label"], entry["url"]) for entry in _social_links(company)]
        try:
            merged = _clean_social_links(existing + incoming)
        except DiscoveryServiceError as exc:
            raise ValueError(str(exc)) from exc
        if merged != _clean_social_links(existing):
            extra = dict(company.extra or {})
            extra["social_links"] = merged
            company.extra = extra
            changed.append("social_links")

    if (
        {"phone", "email", "website_url", "social_links"} & set(changed)
        and company.places_checked_at is None
    ):
        company.places_checked_at = datetime.now(UTC)

    opportunity = ensure_opportunity(session, company)
    status = item.get("status")
    if status:
        if status not in CRM_STATUSES:
            raise ValueError(f"status non valido: {status}")
        if status != opportunity.status:
            session.add(
                Activity(
                    opportunity_id=opportunity.id,
                    type="status_change",
                    note=f"{opportunity.status} → {status} (import JSON)",
                    occurred_at=datetime.now(UTC),
                )
            )
            opportunity.status = status
            changed.append("status")
    if isinstance(item.get("is_favorite"), bool) and item["is_favorite"] != opportunity.is_favorite:
        opportunity.is_favorite = item["is_favorite"]
        changed.append("is_favorite")

    tags = item.get("tags")
    if isinstance(tags, list):
        current = {
            link.tag.name
            for link in session.query(OpportunityTag).filter_by(opportunity_id=opportunity.id).all()
            if link.tag is not None
        }
        for raw in tags:
            name = _normalize_tag(raw)[:64] if isinstance(raw, str) else ""
            if not name or name in current:
                continue
            tag = session.query(Tag).filter_by(name=name).one_or_none()
            if tag is None:
                tag = Tag(name=name)
                session.add(tag)
                session.flush()
            session.add(OpportunityTag(opportunity_id=opportunity.id, tag_id=tag.id))
            current.add(name)
            changed.append("tags")

    new_notes = item.get("new_notes")
    if isinstance(new_notes, list):
        known = {
            note.body for note in session.query(OpportunityNote).filter_by(opportunity_id=opportunity.id).all()
        }
        for raw in new_notes:
            body = raw.strip()[:4000] if isinstance(raw, str) else ""
            if body and body not in known:
                session.add(OpportunityNote(opportunity_id=opportunity.id, body=body))
                known.add(body)
                changed.append("notes")

    return changed


def import_export(session: Session, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("format") != EXPORT_FORMAT:
        raise PipelineImportError("File non valido: non è un export della pipeline RevampRadar.")
    if payload.get("version") != EXPORT_VERSION:
        raise PipelineImportError("Versione del file non supportata.")
    items = payload.get("companies")
    if not isinstance(items, list):
        raise PipelineImportError("File non valido: manca l'elenco 'companies'.")

    updated = unchanged = 0
    errors: list[dict[str, str]] = []
    for index, item in enumerate(items):
        label = _text(item.get("name")) if isinstance(item, dict) else None
        label = label or f"#{index + 1}"
        if not isinstance(item, dict):
            errors.append({"company": label, "error": "Elemento non valido."})
            continue
        company = _find_company(session, item)
        if company is None:
            errors.append({"company": label, "error": "Azienda non trovata."})
            continue
        # Un savepoint per riga: un dato errato non blocca (né sporca) le altre aziende.
        try:
            with session.begin_nested():
                changed = _apply_item(session, company, item)
        except ValueError as exc:
            errors.append({"company": label, "error": str(exc)})
            continue
        if changed:
            updated += 1
        else:
            unchanged += 1
    session.commit()
    return {"total": len(items), "updated": updated, "unchanged": unchanged, "errors": errors}
