"""Inserimento CRM di un'azienda, senza audit né chiamate esterne.

Crea l'azienda e la sua Opportunity nella stessa transazione. La deduplica
distingue una corrispondenza certa da un conflitto: un dominio condiviso, un
numero centralizzato o un'email comune non fondono sedi diverse. Il nome da
solo non identifica un'azienda.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Literal
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.discovery.normalize import normalize_email, normalize_phone, normalize_text
from app.discovery.osm import social_contact_links
from app.discovery.service import DiscoveryServiceError, _clean_social_links
from app.models.entities import Activity, Company, Opportunity, OpportunityNote, OpportunityTag, Tag, Website
from app.scanner.url import UrlValidationError, normalize_url
from app.schemas.company_manual import (
    CompanyImportRow,
    CompanyMatchCandidate,
    EventResult,
    HistoricalEventIn,
    ImportRowResult,
    ManualCompanyCreate,
)
from app.schemas.crm import CRM_STATUSES
from app.services.company_identity import describe, find_identity_duplicates
from app.services.crm_service import _normalize_tag, ensure_opportunity
from app.services.instagram import (
    handle_from_links,
    instagram_profile_url,
    normalize_instagram_handle,
    validate_last_post_date,
)
from app.services.pipeline_io import _social_links

_LOCK = threading.Lock()
# Serializza gli inserimenti anche tra più processi PostgreSQL.
_ADVISORY_KEY = 582019164
_EMAIL = re.compile(r"[^@\s]+@[^@\s.]+(?:\.[^@\s.]+)+")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_EVENT_KINDS = {
    "email_sent": "Email inviata (storico registrato, nessun messaggio spedito da RevampRadar)",
    "dm_sent": "Primo DM solo testo inviato (storico registrato, nessun messaggio spedito da RevampRadar)",
    "concept_sent": "Concept inviato (storico, distinto dal primo DM, nessun messaggio spedito da RevampRadar)",
}
_HOST_NETWORK = {
    "instagram.com": "instagram",
    "facebook.com": "facebook",
    "fb.com": "facebook",
    "tiktok.com": "tiktok",
    "linkedin.com": "linkedin",
    "twitter.com": "x",
    "x.com": "x",
}
_LABEL_NETWORK = {
    "instagram": "instagram",
    "ig": "instagram",
    "facebook": "facebook",
    "fb": "facebook",
    "tiktok": "tiktok",
    "linkedin": "linkedin",
    "twitter": "x",
    "x": "x",
}
_NETWORK_HOST = {
    "instagram": "instagram.com",
    "facebook": "facebook.com",
    "tiktok": "tiktok.com",
    "linkedin": "linkedin.com",
    "x": "x.com",
}
_REASON = {
    "website": "sito normalizzato",
    "email": "email",
    "phone": "telefono",
    "social": "social",
    "name_location": "nome e località",
    "external_id": "identificativo esterno",
    "company_id": "company_id",
    "instagram_handle": "stesso profilo Instagram",
    "domain": "stesso dominio del sito",
    "website_url": "stessa pagina web",
}
_RANK = {
    "discovered": 0,
    "analyzed": 1,
    "qualified": 2,
    "shortlisted": 3,
    "to_contact": 4,
    "contacted": 5,
    "replied": 6,
    "meeting": 7,
    "proposal": 8,
    "won": 9,
}
_EXCLUSIONS = frozenset({"lost", "uncontactable", "not_now"})
_BEFORE_CONTACT = frozenset({"discovered", "analyzed", "qualified", "shortlisted", "to_contact", "contacted"})


class ManualCompanyError(Exception):
    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass
class NormalizedEvent:
    external_ref: str
    kind: str
    channel: str
    sender: str | None
    recipient: str | None
    batch_id: str | None
    occurred_at: datetime | None
    occurred_on: date | None


@dataclass
class NormalizedCompany:
    name: str | None
    name_key: str | None
    website_url: str | None
    website_original: str | None
    domain: str | None
    email: str | None
    phone: str | None
    social_links: list[dict[str, str]]
    social_ids: set[str]
    instagram_handle: str | None
    instagram_last_post_at: date | None
    category: str | None
    city: str | None
    city_key: str | None
    region: str | None
    region_key: str | None
    province: str | None
    province_key: str | None
    country: str | None
    source: str
    external_id: str | None
    status: str | None
    notes: list[str]
    tags: list[str]
    events: list[NormalizedEvent]
    company_id: UUID | None = None
    ref: str | None = None


@dataclass
class _Cand:
    company: Company
    reasons: set[str] = field(default_factory=set)
    strong: bool = False
    weak: bool = False


@dataclass
class Match:
    outcome: Literal["certain", "ambiguous", "none", "id_not_found"]
    company: Company | None = None
    candidates: list[_Cand] = field(default_factory=list)


@dataclass
class WriteOutcome:
    outcome: str
    company: Company | None = None
    candidates: list[_Cand] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    changes: list[str] = field(default_factory=list)
    inserted_events: set[str] = field(default_factory=set)


def create_manual_company(
    session: Session, payload: ManualCompanyCreate
) -> tuple[str, Company | None, list[CompanyMatchCandidate], list[str], str | None]:
    """Crea o restituisce l'azienda. Ritorna outcome, company, candidati, avvisi, errore."""
    data = _normalize(payload, company_id=None, ref=None)
    with _LOCK:
        _advisory(session)
        try:
            if not payload.allow_duplicates:
                duplicates = find_identity_duplicates(
                    session,
                    instagram_handle=data.instagram_handle,
                    website_url=data.website_url,
                    email=data.email,
                )
                if duplicates:
                    candidates = [
                        _candidate(session, _Cand(company=item.company, reasons=set(item.reasons)))
                        for item in duplicates
                    ]
                    session.rollback()
                    return (
                        "duplicate",
                        duplicates[0].company,
                        candidates,
                        [],
                        f"Azienda già presente ({describe(duplicates[0].reasons)}): nessuna scheda creata. "
                        "Per una sede diversa con gli stessi recapiti invia allow_duplicates=true.",
                    )
            written = _write_company(session, data, create_missing=True, write=True)
            if written.outcome == "ambiguous":
                candidates = [_candidate(session, item) for item in written.candidates]
                session.rollback()
                return "conflict", None, candidates, written.warnings, written.error
            session.commit()
            if written.company is not None:
                session.refresh(written.company)
            if written.outcome == "created":
                return "created", written.company, [], written.warnings, None
            return ("updated" if written.changes else "existing"), written.company, [], written.warnings, None
        except IntegrityError:
            session.rollback()
            match = find_match(session, data)
            if match.outcome == "certain" and match.company is not None:
                return "existing", match.company, [], [], None
            raise ManualCompanyError("Inserimento concorrente non risolto.") from None
        except Exception:
            session.rollback()
            raise


def preview_companies(session: Session, rows: list[CompanyImportRow]) -> list[ImportRowResult]:
    """Classifica le righe senza scrivere sul database."""
    return [_row_result(session, item, create_missing=True, write=False) for item in _dedupe_refs(rows)]


def import_companies(
    session: Session, rows: list[CompanyImportRow], *, create_missing: bool
) -> list[ImportRowResult]:
    """Importa le righe. Crea le mancanti solo se create_missing è true."""
    prepared = _dedupe_refs(rows)
    with _LOCK:
        _advisory(session)
        results: list[ImportRowResult] = []
        try:
            for item in prepared:
                if item.outcome == "invalid" or item.data is None:
                    results.append(
                        ImportRowResult(ref=item.ref, outcome="invalid", error=item.error or "Riga non valida.")
                    )
                    continue
                try:
                    with session.begin_nested():
                        result = _row_from_data(session, item.data, create_missing=create_missing, write=True)
                        session.flush()
                        results.append(result)
                except IntegrityError:
                    results.append(_recover_row(session, item.data, item.ref))
                except ManualCompanyError as exc:
                    results.append(ImportRowResult(ref=item.ref, outcome="invalid", error=str(exc)))
            session.commit()
        except Exception:
            session.rollback()
            raise
    return results


@dataclass
class _Prepared:
    ref: str
    outcome: str | None = None
    data: NormalizedCompany | None = None
    error: str | None = None


def _dedupe_refs(rows: list[CompanyImportRow]) -> list[_Prepared]:
    seen: set[str] = set()
    prepared: list[_Prepared] = []
    for row in rows:
        if row.ref in seen:
            prepared.append(_Prepared(ref=row.ref, outcome="invalid", error="Riferimento di riga duplicato."))
            continue
        seen.add(row.ref)
        try:
            prepared.append(_Prepared(ref=row.ref, data=_normalize(row, company_id=row.company_id, ref=row.ref)))
        except ManualCompanyError as exc:
            prepared.append(_Prepared(ref=row.ref, outcome="invalid", error=str(exc)))
    return prepared


def _row_result(
    session: Session,
    prepared: _Prepared,
    *,
    create_missing: bool,
    write: bool,
) -> ImportRowResult:
    if prepared.outcome == "invalid" or prepared.data is None:
        return ImportRowResult(ref=prepared.ref, outcome="invalid", error=prepared.error or "Riga non valida.")
    try:
        return _row_from_data(session, prepared.data, create_missing=create_missing, write=write)
    except ManualCompanyError as exc:
        return ImportRowResult(ref=prepared.ref, outcome="invalid", error=str(exc))


def _row_from_data(
    session: Session, data: NormalizedCompany, *, create_missing: bool, write: bool
) -> ImportRowResult:
    written = _write_company(session, data, create_missing=create_missing, write=write)
    public = _public_outcome(
        written.outcome, write=write, create_missing=create_missing, changes=written.changes
    )
    error = written.error
    if public == "skipped":
        error = "Creazione non richiesta: la riga non corrisponde a un'azienda già presente."
    opportunity = _opportunity_of(session, written.company)
    show_events = public not in {"ambiguous", "invalid", "id_not_found", "skipped"}
    events = (
        _describe_events(
            session,
            opportunity.id if opportunity else None,
            data.events,
            inserted=written.inserted_events,
            write=write and public in {"created", "updated", "existing"},
        )
        if show_events
        else []
    )
    if any(item.outcome == "invalid" for item in events):
        message = next(item.error for item in events if item.error)
        if write:
            raise ManualCompanyError(message or "Evento non valido.")
        return ImportRowResult(
            ref=data.ref or "",
            outcome="invalid",
            error=message,
            warnings=written.warnings,
            events=events,
        )
    return ImportRowResult(
        ref=data.ref or "",
        outcome=public,  # type: ignore[arg-type]
        company_id=written.company.id if written.company is not None else None,
        opportunity_id=opportunity.id if opportunity is not None else None,
        error=error,
        warnings=written.warnings,
        changes=written.changes,
        candidates=[_candidate(session, item) for item in written.candidates],
        events=events,
    )


def _public_outcome(outcome: str, *, write: bool, create_missing: bool, changes: list[str]) -> str:
    if outcome == "created":
        return "created"
    if outcome == "certain":
        if write:
            return "updated" if changes else "existing"
        return "update" if changes else "existing"
    if outcome == "none":
        if not write:
            return "new"
        return "created" if create_missing else "skipped"
    return outcome


def _recover_row(session: Session, data: NormalizedCompany, ref: str) -> ImportRowResult:
    match = find_match(session, data)
    if match.outcome == "certain" and match.company is not None:
        opportunity = _opportunity_of(session, match.company)
        return ImportRowResult(
            ref=ref,
            outcome="existing",
            company_id=match.company.id,
            opportunity_id=opportunity.id if opportunity else None,
            warnings=["Inserimento concorrente risolto sulla scheda già presente."],
        )
    return ImportRowResult(ref=ref, outcome="invalid", error="Inserimento concorrente non risolto.")


def _write_company(
    session: Session,
    data: NormalizedCompany,
    *,
    create_missing: bool,
    write: bool,
) -> WriteOutcome:
    match = find_match(session, data)
    if match.outcome == "id_not_found":
        return WriteOutcome(
            outcome="id_not_found",
            error="company_id inesistente: nessuna corrispondenza verificata, azienda non creata.",
        )
    if match.outcome == "ambiguous":
        return WriteOutcome(
            outcome="ambiguous",
            candidates=match.candidates,
            error="Corrispondenza ambigua: nessuna azienda creata o fusa.",
        )
    if match.outcome == "none":
        if not data.name:
            raise ManualCompanyError("Il nome è obbligatorio.")
        foreign = _foreign_event_error(session, None, data.events)
        if foreign:
            raise ManualCompanyError(foreign)
        if not write or not create_missing:
            return WriteOutcome(outcome="none", changes=_create_field_names(data))
        company = _insert_company(session, data)
        inserted = _store_events(session, _require_opportunity(session, company), data)
        return WriteOutcome(
            outcome="created",
            company=company,
            changes=_create_field_names(data),
            inserted_events=inserted,
        )
    company = match.company
    assert company is not None
    opportunity = session.query(Opportunity).filter_by(company_id=company.id).one_or_none()
    foreign = _foreign_event_error(session, opportunity.id if opportunity else None, data.events)
    if foreign:
        raise ManualCompanyError(foreign)
    if opportunity is None and write:
        opportunity = ensure_opportunity(session, company)
    changes, warnings, _conflict = _apply_updates(session, company, opportunity, data, write=write)
    inserted: set[str] = set()
    if write and opportunity is not None:
        inserted = _store_events(session, opportunity, data)
    return WriteOutcome(
        outcome="certain",
        company=company,
        warnings=warnings,
        changes=changes,
        inserted_events=inserted,
    )


def find_match(session: Session, data: NormalizedCompany) -> Match:
    grouped: dict[UUID, _Cand] = {}

    def add(company: Company | None, reason: str, strong: bool) -> None:
        if company is None:
            return
        cand = grouped.get(company.id)
        if cand is None:
            cand = _Cand(company=company)
            grouped[company.id] = cand
        cand.reasons.add(reason)
        if strong:
            cand.strong = True
        else:
            cand.weak = True

    if data.company_id is not None:
        named = session.get(Company, data.company_id)
        if named is None:
            others = _signal_match(session, data, grouped={})
            if others.outcome == "certain":
                return others
            if others.outcome == "ambiguous":
                return others
            return Match(outcome="id_not_found")
        add(named, "company_id", True)

    if data.external_id:
        found = (
            session.query(Company)
            .filter_by(source=data.source, external_id=data.external_id)
            .one_or_none()
        )
        if found is not None:
            both_differ = _name_conflict(found, data) and _locality_conflict(found, data)
            add(found, "external_id", not both_differ)

    for company in _website_companies(session, data.website_url):
        add(company, "website", _shared_strong(company, data))
    if data.email:
        for company in session.query(Company).filter(Company.email == data.email).all():
            add(company, "email", _shared_strong(company, data))
    if data.phone:
        for company in session.query(Company).filter(Company.phone == data.phone).all():
            add(company, "phone", _shared_strong(company, data))
    for company, strong in _social_companies(session, data.social_ids):
        add(company, "social", strong and _shared_strong(company, data))
    for company in _name_location_companies(session, data):
        add(company, "name_location", True)

    return _decide(list(grouped.values()))


def _signal_match(session: Session, data: NormalizedCompany, grouped: dict[UUID, _Cand]) -> Match:
    del grouped
    saved = data.company_id
    data.company_id = None
    try:
        return find_match(session, data)
    finally:
        data.company_id = saved


def _decide(cands: list[_Cand]) -> Match:
    strong = [item for item in cands if item.strong]
    weak_only = [item for item in cands if item.weak and not item.strong]
    if len(strong) == 1 and not weak_only:
        return Match(outcome="certain", company=strong[0].company)
    if strong or weak_only:
        return Match(outcome="ambiguous", candidates=sorted(cands, key=lambda item: item.company.name.casefold()))
    return Match(outcome="none")


def _shared_strong(company: Company, data: NormalizedCompany) -> bool:
    """Un identificativo condiviso è certo solo se nome e località non lo contraddicono."""
    if _name_conflict(company, data) or _locality_conflict(company, data):
        return False
    if not data.name_key:
        return False
    if _key(company.name) != data.name_key:
        return False
    if _key(company.city) and not data.city_key:
        return False
    return True


def _name_conflict(company: Company, data: NormalizedCompany) -> bool:
    return bool(data.name_key and _key(company.name) and data.name_key != _key(company.name))


def _locality_conflict(company: Company, data: NormalizedCompany) -> bool:
    if data.city_key and _key(company.city) and data.city_key != _key(company.city):
        return True
    company_province = _province_key(company)
    if data.province_key and company_province and data.province_key != company_province:
        if not (data.city_key and _key(company.city) == data.city_key):
            return True
    return False


def _website_companies(session: Session, website_url: str | None) -> list[Company]:
    if not website_url:
        return []
    found: dict[UUID, Company] = {}
    for company in session.query(Company).filter(Company.website_url == website_url).all():
        found[company.id] = company
    for website in session.query(Website).filter(Website.normalized_url == website_url).all():
        if website.company_id is None:
            continue
        company = session.get(Company, website.company_id)
        if company is not None:
            found[company.id] = company
    return list(found.values())


def _social_companies(session: Session, identities: set[str]) -> list[tuple[Company, bool]]:
    if not identities:
        return []
    hits: list[tuple[Company, bool]] = []
    for company in session.query(Company).filter(Company.extra.is_not(None)).all():
        known = _company_social_ids(company)
        if known & identities:
            hits.append((company, True))
    return hits


def _name_location_companies(session: Session, data: NormalizedCompany) -> list[Company]:
    if not data.name_key:
        return []
    if data.city_key:
        return [
            company
            for company in session.query(Company).all()
            if _key(company.name) == data.name_key and _key(company.city) == data.city_key
        ]
    if data.province_key:
        return [
            company
            for company in session.query(Company).all()
            if _key(company.name) == data.name_key
            and not _key(company.city)
            and _province_key(company) == data.province_key
        ]
    if data.region_key:
        return [
            company
            for company in session.query(Company).all()
            if _key(company.name) == data.name_key
            and not _key(company.city)
            and not _province_key(company)
            and _key(company.region) == data.region_key
        ]
    return []


def _insert_company(session: Session, data: NormalizedCompany) -> Company:
    assert data.name is not None
    extra: dict | None = {}
    if data.social_links:
        extra["social_links"] = data.social_links
    if data.province:
        extra["province"] = data.province
    company = Company(
        name=data.name[:255],
        category=data.category,
        city=data.city,
        region=data.region,
        country=data.country,
        website_url=data.website_url,
        phone=data.phone,
        email=data.email,
        instagram_handle=data.instagram_handle,
        instagram_last_post_at=data.instagram_last_post_at,
        source=data.source,
        external_id=data.external_id,
        status="discovered",
        extra=extra or None,
    )
    session.add(company)
    session.flush()
    opportunity = ensure_opportunity(session, company)
    status, conflict = _initial_status(data)
    opportunity.status = status
    if data.website_url and data.website_original and data.domain:
        _attach_website(session, company, data.website_url, data.website_original, data.domain)
    _add_notes(session, opportunity, data.notes)
    _add_tags(session, opportunity, data.tags)
    if conflict:
        _add_note_once(session, opportunity, conflict)
    return company


def _apply_updates(
    session: Session,
    company: Company,
    opportunity: Opportunity | None,
    data: NormalizedCompany,
    *,
    write: bool,
) -> tuple[list[str], list[str], str | None]:
    changes: list[str] = []
    warnings: list[str] = []

    def fill(field_name: str, value: str | None, limit: int) -> None:
        if not value:
            return
        current = getattr(company, field_name)
        clipped = value[:limit]
        if not current:
            changes.append(field_name)
            if write:
                setattr(company, field_name, clipped)
        elif current != clipped:
            warnings.append(f"{field_name} già presente, lasciato invariato.")

    fill("category", data.category, 128)
    fill("city", data.city, 128)
    fill("region", data.region, 128)
    fill("country", data.country, 64)
    if data.name and _key(company.name) != data.name_key:
        warnings.append("Nome diverso da quello già in scheda, lasciato invariato.")
    if data.website_url:
        if not company.website_url:
            changes.append("website_url")
            if write:
                company.website_url = data.website_url
                if data.website_original and data.domain:
                    _attach_website(session, company, data.website_url, data.website_original, data.domain)
        elif company.website_url != data.website_url:
            warnings.append("Sito già presente, lasciato invariato.")
    fill("phone", data.phone, 64)
    fill("email", data.email, 255)
    fill("instagram_handle", data.instagram_handle, 64)
    if data.instagram_last_post_at is not None:
        current_post = company.instagram_last_post_at
        if current_post is None or data.instagram_last_post_at > current_post:
            # L'ultimo post va avanti nel tempo: una data più recente aggiorna quella salvata.
            changes.append("instagram_last_post_at")
            if write:
                company.instagram_last_post_at = data.instagram_last_post_at
        elif data.instagram_last_post_at < current_post:
            warnings.append(
                f"Ultimo post Instagram già registrato al {current_post.isoformat()}: "
                "la data più vecchia è stata ignorata."
            )
    if data.province:
        current_province = _province_text(company)
        if not current_province:
            changes.append("province")
            if write:
                _put_extra(company, "province", data.province)
        elif current_province != data.province:
            warnings.append("Provincia già presente, lasciata invariata.")
    if data.social_links:
        merged = _merge_social(company, data.social_links)
        current = _clean_existing_social(company)
        if merged != current:
            changes.append("social_links")
            if write:
                _put_extra(company, "social_links", merged)
    known_notes = _note_bodies(session, opportunity) if opportunity is not None else set()
    new_notes = [note for note in data.notes if note not in known_notes]
    if new_notes:
        changes.append("notes")
        if write and opportunity is not None:
            _add_notes(session, opportunity, new_notes)
    known_tags = _tag_names(session, opportunity) if opportunity is not None else set()
    new_tags = [tag for tag in data.tags if tag not in known_tags]
    if new_tags:
        changes.append("tags")
        if write and opportunity is not None:
            _add_tags(session, opportunity, new_tags)
    if data.external_id and not company.external_id and company.source == data.source:
        changes.append("external_id")
        if write:
            company.external_id = data.external_id
    current_status = opportunity.status if opportunity is not None else "discovered"
    new_status, conflict = _next_status(current_status, data)
    if new_status != current_status:
        changes.append("status")
        if write and opportunity is not None:
            previous = opportunity.status
            opportunity.status = new_status
            session.add(
                Activity(
                    opportunity_id=opportunity.id,
                    type="status_change",
                    note=f"{previous} → {new_status} (inserimento manuale)",
                    occurred_at=datetime.now(UTC),
                )
            )
    elif data.status and data.status != current_status and conflict is None and not data.events:
        warnings.append(f"Stato «{current_status}» conservato: «{data.status}» non lo retrocede.")
    if conflict:
        warnings.append(conflict)
        if conflict not in known_notes and "notes" not in changes:
            changes.append("notes")
        if write and opportunity is not None and conflict not in known_notes:
            _add_note_once(session, opportunity, conflict)
    event_changes = _new_event_refs(session, opportunity.id if opportunity else None, data.events)
    if event_changes:
        changes.append("events")
    return changes, warnings, conflict


def _initial_status(data: NormalizedCompany) -> tuple[str, str | None]:
    requested = data.status or "discovered"
    if not data.events:
        return requested, None
    if requested in _EXCLUSIONS or _RANK.get(requested, -1) > _RANK["contacted"]:
        return requested, _conflict_text(requested)
    return "contacted", None


def _next_status(current: str, data: NormalizedCompany) -> tuple[str, str | None]:
    target = data.status
    history = bool(data.events)
    if history and (target is None or target in _BEFORE_CONTACT):
        target = "contacted"
    if target is None or target == current:
        if history and current != "contacted" and _RANK.get(current, -1) > _RANK["contacted"]:
            return current, _conflict_text(current)
        if history and current in _EXCLUSIONS:
            return current, _conflict_text(current)
        return current, None
    if current in _EXCLUSIONS:
        return current, _conflict_text(current) if history else None
    if target in _EXCLUSIONS:
        if current in _RANK and _RANK[current] >= _RANK["contacted"]:
            return current, _conflict_text(current) if history else None
        return target, None
    if target not in _RANK or current not in _RANK:
        return current, _conflict_text(current) if history else None
    if _RANK[target] > _RANK[current]:
        return target, None
    if history and current != "contacted":
        return current, _conflict_text(current)
    return current, None


def _conflict_text(status: str) -> str:
    return (
        "Conflitto da verificare: c'è un invio storico, ma lo stato "
        f"«{status}» resta com'è e non viene portato a contacted."
    )


def _store_events(session: Session, opportunity: Opportunity, data: NormalizedCompany) -> set[str]:
    inserted: set[str] = set()
    for event in data.events:
        existing = session.query(Activity).filter_by(external_ref=event.external_ref).one_or_none()
        if existing is not None:
            if existing.opportunity_id != opportunity.id:
                raise ManualCompanyError(
                    f"Il riferimento evento {event.external_ref} appartiene già a un'altra azienda."
                )
            continue
        session.add(
            Activity(
                opportunity_id=opportunity.id,
                type=event.kind,
                note=_event_note(event),
                occurred_at=event.occurred_at,
                occurred_on=event.occurred_on,
                channel=event.channel,
                sender=event.sender,
                recipient=event.recipient,
                batch_id=event.batch_id,
                external_ref=event.external_ref,
            )
        )
        inserted.add(event.external_ref)
    return inserted


def _describe_events(
    session: Session,
    opportunity_id: UUID | None,
    events: list[NormalizedEvent],
    *,
    inserted: set[str],
    write: bool,
) -> list[EventResult]:
    results: list[EventResult] = []
    seen: set[str] = set()
    for event in events:
        if event.external_ref in seen:
            results.append(
                EventResult(
                    external_ref=event.external_ref,
                    outcome="invalid",
                    error="Riferimento duplicato nella riga.",
                )
            )
            continue
        seen.add(event.external_ref)
        if event.external_ref in inserted:
            results.append(
                EventResult(
                    external_ref=event.external_ref,
                    outcome="recorded" if write else "would_record",
                )
            )
            continue
        existing = session.query(Activity).filter_by(external_ref=event.external_ref).one_or_none()
        if existing is None:
            results.append(EventResult(external_ref=event.external_ref, outcome="would_record"))
        elif opportunity_id is not None and existing.opportunity_id == opportunity_id:
            results.append(EventResult(external_ref=event.external_ref, outcome="duplicate"))
        else:
            results.append(
                EventResult(
                    external_ref=event.external_ref,
                    outcome="invalid",
                    error="Riferimento già usato da un'altra azienda.",
                )
            )
    return results


def _foreign_event_error(session: Session, opportunity_id: UUID | None, events: list[NormalizedEvent]) -> str | None:
    seen: set[str] = set()
    for event in events:
        if event.external_ref in seen:
            return "Riferimento evento duplicato nella riga."
        seen.add(event.external_ref)
        existing = session.query(Activity).filter_by(external_ref=event.external_ref).one_or_none()
        if existing is not None and (opportunity_id is None or existing.opportunity_id != opportunity_id):
            return f"Il riferimento evento {event.external_ref} appartiene già a un'altra azienda."
    return None


def _new_event_refs(session: Session, opportunity_id: UUID | None, events: list[NormalizedEvent]) -> list[str]:
    fresh: list[str] = []
    for event in events:
        existing = session.query(Activity).filter_by(external_ref=event.external_ref).one_or_none()
        if existing is None:
            fresh.append(event.external_ref)
        elif opportunity_id is None or existing.opportunity_id != opportunity_id:
            raise ManualCompanyError(
                f"Il riferimento evento {event.external_ref} appartiene già a un'altra azienda."
            )
    return fresh


def _event_note(event: NormalizedEvent) -> str:
    parts = [_EVENT_KINDS[event.kind], f"Canale: {event.channel}"]
    if event.sender:
        parts.append(f"Mittente: {event.sender}")
    if event.recipient:
        parts.append(f"Destinatario: {event.recipient}")
    if event.batch_id:
        parts.append(f"Lotto: {event.batch_id}")
    parts.append(f"Rif: {event.external_ref}")
    return ". ".join(parts)


def _normalize(payload: ManualCompanyCreate, *, company_id: UUID | None, ref: str | None) -> NormalizedCompany:
    name = _clip(normalize_text(payload.name), 255)
    source = _clip(normalize_text(payload.source), 64) or "manual"
    website_url = None
    website_original = None
    domain = None
    raw_site = _blank(payload.website_url)
    if raw_site:
        try:
            normalized = normalize_url(raw_site)
        except UrlValidationError as exc:
            raise ManualCompanyError(str(exc)) from exc
        website_url = normalized.normalized
        website_original = normalized.original
        domain = normalized.domain
    email = None
    raw_email = _blank(payload.email)
    if raw_email:
        email = normalize_email(raw_email)
        if email is None or _EMAIL.fullmatch(email) is None:
            raise ManualCompanyError(f"Email non valida: {raw_email}")
    phone = None
    raw_phone = _blank(payload.phone)
    if raw_phone:
        phone = normalize_phone(raw_phone)
        if not phone:
            raise ManualCompanyError("Telefono non valido.")
        phone = phone[:64]
    raw_links = [(item.label, item.url) for item in payload.social_links]
    try:
        instagram_handle = normalize_instagram_handle(payload.instagram_handle)
        instagram_last_post_at = validate_last_post_date(payload.instagram_last_post_at)
    except ValueError as exc:
        raise ManualCompanyError(str(exc)) from exc
    if instagram_handle is None:
        instagram_handle = handle_from_links(raw_links)
    elif handle_from_links(raw_links) is None:
        # Il profilo entra anche fra i social: la deduplica per social riconosce lo stesso account.
        raw_links.append(("Instagram", instagram_profile_url(instagram_handle)))
    social_links, social_ids = _prepare_social(raw_links)
    status = _blank(payload.status)
    if status is not None and status not in CRM_STATUSES:
        raise ManualCompanyError(f"Stato CRM non valido: {status}")
    notes = _unique_texts(payload.notes, 4000)
    tags: list[str] = []
    for raw_tag in payload.tags:
        if not isinstance(raw_tag, str):
            continue
        normalized_tag = _normalize_tag(raw_tag)[:64]
        if normalized_tag and normalized_tag not in tags:
            tags.append(normalized_tag)
    events = [_normalize_event(item) for item in payload.events]
    external_id = _clip(normalize_text(payload.external_id), 128)
    return NormalizedCompany(
        name=name,
        name_key=_key(name),
        website_url=website_url,
        website_original=website_original,
        domain=domain,
        email=email,
        phone=phone,
        social_links=social_links,
        social_ids=social_ids,
        instagram_handle=instagram_handle,
        instagram_last_post_at=instagram_last_post_at,
        category=_clip(normalize_text(payload.category), 128),
        city=_clip(normalize_text(payload.city), 128),
        city_key=_key(payload.city),
        region=_clip(normalize_text(payload.region), 128),
        region_key=_key(payload.region),
        province=_clip(normalize_text(payload.province), 128),
        province_key=_key(payload.province),
        country=_clip(normalize_text(payload.country), 64),
        source=source,
        external_id=external_id,
        status=status,
        notes=notes,
        tags=tags,
        events=events,
        company_id=company_id,
        ref=ref,
    )


def _normalize_event(payload: HistoricalEventIn) -> NormalizedEvent:
    kind = payload.kind.strip()
    if kind not in _EVENT_KINDS:
        raise ManualCompanyError(
            "Tipo evento non valido. Ammessi: email_sent, dm_sent, concept_sent. "
            "Invio, consegna, lettura e risposta restano eventi distinti."
        )
    channel = _clip(normalize_text(payload.channel), 32)
    if not channel:
        raise ManualCompanyError("Canale dell'evento obbligatorio.")
    external_ref = _clip(normalize_text(payload.external_ref), 255)
    if not external_ref:
        raise ManualCompanyError("Riferimento esterno dell'evento obbligatorio.")
    occurred_at, occurred_on = _parse_when(payload.occurred_at, payload.occurred_on)
    return NormalizedEvent(
        external_ref=external_ref,
        kind=kind,
        channel=channel,
        sender=_clip(normalize_text(payload.sender), 255),
        recipient=_clip(normalize_text(payload.recipient), 255),
        batch_id=_clip(normalize_text(payload.batch_id), 128),
        occurred_at=occurred_at,
        occurred_on=occurred_on,
    )


def _parse_when(occurred_at: str | None, occurred_on: str | None) -> tuple[datetime | None, date | None]:
    raw_at = _blank(occurred_at)
    raw_on = _blank(occurred_on)
    if raw_at and raw_on:
        raise ManualCompanyError("Indicare solo occurred_at oppure occurred_on.")
    if raw_on:
        if _DATE.fullmatch(raw_on) is None:
            raise ManualCompanyError("occurred_on deve essere una data YYYY-MM-DD, senza orario.")
        return None, date.fromisoformat(raw_on)
    if raw_at:
        if _DATE.fullmatch(raw_at):
            raise ManualCompanyError("Data senza orario: usare occurred_on, non occurred_at.")
        try:
            parsed = datetime.fromisoformat(raw_at)
        except ValueError as exc:
            raise ManualCompanyError("occurred_at non valido.") from exc
        if parsed.tzinfo is None:
            raise ManualCompanyError("occurred_at deve includere il fuso orario: l'orario non viene inventato.")
        return parsed.astimezone(UTC), None
    raise ManualCompanyError("Manca la data reale dell'evento.")


def _prepare_social(links: list[tuple[str, str]]) -> tuple[list[dict[str, str]], set[str]]:
    canonical: list[tuple[str, str]] = []
    for label, raw in links:
        text_url = _blank(raw)
        if not text_url:
            continue
        canonical.append((_blank(label) or "", _canonical_social(label, text_url)))
    if not canonical:
        return [], set()
    try:
        cleaned = _clean_social_links(canonical)
    except DiscoveryServiceError as exc:
        raise ManualCompanyError(str(exc)) from exc
    identities: set[str] = set()
    for item in cleaned:
        identity = social_identity(item["label"], item["url"])
        if identity:
            identities.add(identity)
    return cleaned, identities


def _canonical_social(label: str, raw: str) -> str:
    network = _LABEL_NETWORK.get(label.strip().casefold())
    text_url = raw.strip()
    handle = text_url[1:] if text_url.startswith("@") else text_url
    if network and "://" not in text_url and "/" not in handle and "." not in handle and " " not in handle:
        return f"https://{_NETWORK_HOST[network]}/{handle.lstrip('@')}"
    return text_url


def social_identity(label: str, raw: str) -> str | None:
    try:
        url = _canonical_social(label, raw)
        if "://" not in url:
            url = f"https://{url}"
        parsed = urlparse(url)
    except ValueError:
        return None
    host = (parsed.hostname or "").lower().removeprefix("www.")
    network = _HOST_NETWORK.get(host)
    if network is None:
        return None
    handle = _handle(network, parsed.path, parsed.query)
    if not handle:
        return None
    return f"{network}:{handle}"


def _handle(network: str, path: str, query: str) -> str | None:
    parts = [part for part in path.split("/") if part]
    if network == "instagram":
        if not parts or parts[0].casefold() in {"p", "reel", "reels", "stories", "explore"}:
            return None
        return parts[0].lstrip("@").casefold()
    if network == "tiktok":
        if not parts:
            return None
        return parts[0].lstrip("@").casefold()
    if network == "linkedin":
        if len(parts) >= 2 and parts[0].casefold() in {"in", "company"}:
            return f"{parts[0].casefold()}/{parts[1].casefold()}"
        return None
    if network == "facebook" and "profile.php" in path and "id=" in query:
        for chunk in query.split("&"):
            if chunk.startswith("id=") and chunk[3:]:
                return f"id:{chunk[3:].casefold()}"
        return None
    if not parts or parts[0].casefold() in {"pages", "groups", "share", "sharer"}:
        return None
    return parts[0].lstrip("@").casefold()


def _company_social_ids(company: Company) -> set[str]:
    found: set[str] = set()
    for item in _social_links(company):
        identity = social_identity(item.get("label", ""), item.get("url", ""))
        if identity:
            found.add(identity)
    extra = company.extra or {}
    tags = extra.get("osm_tags") if isinstance(extra.get("osm_tags"), dict) else None
    for label, url in social_contact_links(tags):
        identity = social_identity(label, url)
        if identity:
            found.add(identity)
    return found


def _merge_social(company: Company, incoming: list[dict[str, str]]) -> list[dict[str, str]]:
    existing = [(item["label"], item["url"]) for item in _social_links(company)]
    added = [(item["label"], item["url"]) for item in incoming]
    try:
        return _clean_social_links(existing + added)
    except DiscoveryServiceError as exc:
        raise ManualCompanyError(str(exc)) from exc


def _clean_existing_social(company: Company) -> list[dict[str, str]]:
    try:
        return _clean_social_links([(item["label"], item["url"]) for item in _social_links(company)])
    except DiscoveryServiceError as exc:
        raise ManualCompanyError(str(exc)) from exc


def _attach_website(session: Session, company: Company, normalized_url: str, original: str, domain: str) -> None:
    website = session.query(Website).filter_by(normalized_url=normalized_url).one_or_none()
    if website is None:
        session.add(
            Website(
                company_id=company.id,
                url=original,
                normalized_url=normalized_url,
                domain=domain,
            )
        )
        return
    if website.company_id is None:
        website.company_id = company.id
        return
    if website.company_id != company.id:
        raise ManualCompanyError("Il sito normalizzato appartiene già a un'altra azienda.")


def _add_notes(session: Session, opportunity: Opportunity, notes: list[str]) -> None:
    known = _note_bodies(session, opportunity)
    for body in notes:
        if body in known:
            continue
        session.add(OpportunityNote(opportunity_id=opportunity.id, body=body))
        known.add(body)


def _add_note_once(session: Session, opportunity: Opportunity, body: str) -> None:
    _add_notes(session, opportunity, [body])


def _note_bodies(session: Session, opportunity: Opportunity) -> set[str]:
    return {
        note.body
        for note in session.query(OpportunityNote).filter_by(opportunity_id=opportunity.id).all()
    }


def _add_tags(session: Session, opportunity: Opportunity, tags: list[str]) -> None:
    current = _tag_names(session, opportunity)
    for name in tags:
        if name in current:
            continue
        tag = session.query(Tag).filter_by(name=name).one_or_none()
        if tag is None:
            tag = Tag(name=name)
            session.add(tag)
            session.flush()
        session.add(OpportunityTag(opportunity_id=opportunity.id, tag_id=tag.id))
        current.add(name)


def _tag_names(session: Session, opportunity: Opportunity) -> set[str]:
    return {
        link.tag.name
        for link in session.query(OpportunityTag).filter_by(opportunity_id=opportunity.id).all()
        if link.tag is not None
    }


def _require_opportunity(session: Session, company: Company) -> Opportunity:
    return ensure_opportunity(session, company)


def _opportunity_of(session: Session, company: Company | None) -> Opportunity | None:
    if company is None:
        return None
    return session.query(Opportunity).filter_by(company_id=company.id).one_or_none()


def _candidate(session: Session, cand: _Cand) -> CompanyMatchCandidate:
    company = cand.company
    opportunity = _opportunity_of(session, company)
    return CompanyMatchCandidate(
        company_id=company.id,
        opportunity_id=opportunity.id if opportunity else None,
        name=company.name,
        city=company.city,
        region=company.region,
        website_url=company.website_url,
        email=company.email,
        phone=company.phone,
        reasons=sorted(_REASON[reason] for reason in cand.reasons),
    )


def _create_field_names(data: NormalizedCompany) -> list[str]:
    names = ["name"]
    for label, value in (
        ("website_url", data.website_url),
        ("email", data.email),
        ("phone", data.phone),
        ("social_links", data.social_links),
        ("category", data.category),
        ("city", data.city),
        ("region", data.region),
        ("province", data.province),
        ("country", data.country),
        ("source", data.source),
        ("status", data.status),
        ("notes", data.notes),
        ("tags", data.tags),
        ("events", data.events),
    ):
        if value:
            names.append(label)
    return names


def _put_extra(company: Company, key: str, value: object) -> None:
    extra = dict(company.extra or {})
    extra[key] = value
    company.extra = extra


def _province_text(company: Company) -> str | None:
    extra = company.extra or {}
    value = extra.get("province")
    return value if isinstance(value, str) and value.strip() else None


def _province_key(company: Company) -> str | None:
    return _key(_province_text(company))


def _unique_texts(values: list[str], limit: int) -> list[str]:
    result: list[str] = []
    for raw in values:
        if not isinstance(raw, str):
            continue
        text_value = normalize_text(raw)
        if not text_value:
            continue
        clipped = text_value[:limit]
        if clipped not in result:
            result.append(clipped)
    return result


def _key(value: str | None) -> str | None:
    text_value = normalize_text(value)
    return text_value.casefold() if text_value else None


def _blank(value: str | None) -> str | None:
    if value is None:
        return None
    text_value = value.strip()
    return text_value or None


def _clip(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    return value[:limit]


def _advisory(session: Session) -> None:
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": _ADVISORY_KEY})
