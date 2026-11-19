from __future__ import annotations

from datetime import UTC, date, datetime
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import Text, cast, func, or_
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    Activity,
    Company,
    GrowthScore,
    Opportunity,
    OpportunityNote,
    OpportunityScore,
    OpportunityTag,
    Tag,
    Website,
)
from app.schemas.crm import ACTIVITY_TYPES, CRM_STATUSES, SCHEDULED_ACTIVITY_TYPES
from app.services.contactability import is_contactable
from app.services.instagram import INSTAGRAM_CHANNELS, effective_instagram_handle


class CrmServiceError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def ensure_opportunity(session: Session, company: Company) -> Opportunity:
    existing = session.query(Opportunity).filter_by(company_id=company.id).one_or_none()
    if existing is not None:
        return existing
    opportunity = Opportunity(company_id=company.id, status="discovered", is_favorite=False)
    session.add(opportunity)
    session.flush()
    return opportunity


def backfill_orphan_websites(session: Session) -> None:
    """Siti già analizzati senza azienda (analisi singole precedenti): li porta in pipeline."""
    from app.models.entities import Website
    from app.services.audit_service import _create_manual_company

    orphans = (
        session.query(Website)
        .filter(Website.company_id.is_(None), Website.audits.any())
        .all()
    )
    for website in orphans:
        website.company_id = _create_manual_company(session, website).id
    if orphans:
        session.commit()


def backfill_opportunities(session: Session) -> None:
    backfill_orphan_websites(session)
    missing = session.query(Company).outerjoin(Opportunity).filter(Opportunity.id.is_(None)).all()
    for company in missing:
        session.add(Opportunity(company_id=company.id, status="discovered", is_favorite=False))
    if missing:
        session.commit()


def mark_analyzed_if_discovered(session: Session, company_id: UUID) -> None:
    company = session.get(Company, company_id)
    if company is None:
        return
    opportunity = ensure_opportunity(session, company)
    if opportunity.status != "discovered":
        return
    opportunity.status = "analyzed"
    session.add(
        Activity(
            opportunity_id=opportunity.id,
            type="status_change",
            note="Passata ad analyzed dopo l'audit.",
            occurred_at=datetime.now(UTC),
        )
    )


def mark_uncontactable_after_places_check(session: Session, company: Company) -> None:
    if company.website_url or company.websites or company.phone or company.email:
        return
    opportunity = ensure_opportunity(session, company)
    tag = session.query(Tag).filter_by(name="nd").one_or_none()
    if tag is None:
        tag = Tag(name="nd")
        session.add(tag)
        session.flush()
    tag_link = session.query(OpportunityTag).filter_by(
        opportunity_id=opportunity.id,
        tag_id=tag.id,
    ).one_or_none()
    if tag_link is None:
        session.add(OpportunityTag(opportunity_id=opportunity.id, tag_id=tag.id))

    note = "Verifica Google Places completata: nessun sito, email o numero di telefono disponibile."
    existing_note = session.query(OpportunityNote).filter_by(
        opportunity_id=opportunity.id,
        body=note,
    ).one_or_none()
    if existing_note is None:
        session.add(OpportunityNote(opportunity_id=opportunity.id, body=note))

    if opportunity.status != "uncontactable":
        previous = opportunity.status
        opportunity.status = "uncontactable"
        session.add(
            Activity(
                opportunity_id=opportunity.id,
                type="status_change",
                note=f"{previous} → uncontactable: Google Places non ha trovato sito, email o telefono.",
                occurred_at=datetime.now(UTC),
            )
        )


# Alias espliciti: niente stemming che possa unire settori diversi (es. bar/barbiere).
_CATEGORY_ALIASES = {
    "barbieri": "barbiere",
    "hotels": "hotel",
    "albergo": "hotel",
    "alberghi": "hotel",
    "ristoranti": "ristorante",
    "restaurant": "ristorante",
    "parrucchieri": "parrucchiere",
    "hairdresser": "parrucchiere",
    "abbigliamento": "abbigliamento",
    "clothes": "abbigliamento",
}


def normalize_category(value: str | None) -> str:
    normalized = " ".join((value or "").casefold().split())
    return _CATEGORY_ALIASES.get(normalized, normalized)


def list_opportunities(
    session: Session,
    *,
    status: str | None = None,
    favorite: bool | None = None,
    shortlist: bool = False,
    query: str | None = None,
    category: str | None = None,
    city: str | None = None,
    tag: str | None = None,
    min_score: int | None = None,
    priority: str | None = None,
    segment: str | None = None,
    contactable: bool | None = None,
    domain: str | None = None,
    channel: str | None = None,
    last_post_after: date | None = None,
) -> list[Opportunity]:
    backfill_opportunities(session)
    q = (
        session.query(Opportunity)
        .join(Company)
        .options(
            selectinload(Opportunity.company).selectinload(Company.websites),
            selectinload(Opportunity.tag_links).selectinload(OpportunityTag.tag),
        )
    )
    if status:
        if status not in CRM_STATUSES:
            raise CrmServiceError("Stato CRM non valido.", status_code=422)
        q = q.filter(Opportunity.status == status)
    if favorite is True:
        q = q.filter(Opportunity.is_favorite.is_(True))
    if shortlist:
        q = q.filter(or_(Opportunity.is_favorite.is_(True), Opportunity.status == "shortlisted"))
    needle = (query or "").strip().lower()
    if needle:
        # Nome, dominio/URL del sito, handle Instagram e link social. Il prefiltro SQL su `extra`
        # è largo (contiene anche i tag OSM); il controllo esatto è in _matches_text.
        core = _like_escape(needle.lstrip("@") or needle)
        pattern = f"%{core}%"
        q = q.filter(
            or_(
                func.lower(Company.name).like(f"%{_like_escape(needle)}%", escape="\\"),
                func.lower(Company.name).like(pattern, escape="\\"),
                func.lower(Company.website_url).like(pattern, escape="\\"),
                Company.websites.any(func.lower(Website.domain).like(pattern, escape="\\")),
                func.lower(Company.instagram_handle).like(pattern, escape="\\"),
                func.lower(cast(Company.extra, Text)).like(pattern, escape="\\"),
            )
        )
    if city:
        q = q.filter(func.lower(Company.city).like(f"%{city.strip().lower()}%"))
    if tag:
        q = q.join(Opportunity.tag_links).join(OpportunityTag.tag).filter(Tag.name == _normalize_tag(tag))
    wanted_domain = None
    if domain is not None and domain.strip():
        wanted_domain = normalize_domain(domain)
        if wanted_domain is None:
            raise CrmServiceError("Dominio non valido: usa la forma esempio.it.", status_code=422)
        # Prefiltro SQL largo, poi confronto esatto in Python sull'host (www. ignorato).
        q = q.filter(
            or_(
                Company.websites.any(func.lower(Website.domain).in_([wanted_domain, f"www.{wanted_domain}"])),
                func.lower(Company.website_url).like(f"%{_like_escape(wanted_domain)}%", escape="\\"),
            )
        )
    instagram_only = False
    if channel is not None and channel.strip():
        if channel.strip().lower() not in INSTAGRAM_CHANNELS:
            raise CrmServiceError("Canale non supportato: usa channel=ig.", status_code=422)
        instagram_only = True
        q = q.filter(
            or_(
                Company.instagram_handle.isnot(None),
                func.lower(cast(Company.extra, Text)).like("%instagram%"),
            )
        )
    if last_post_after is not None:
        # Dal giorno indicato compreso.
        q = q.filter(Company.instagram_last_post_at >= last_post_after)
    if segment not in (None, "all", "refactor", "greenfield"):
        raise CrmServiceError("Segmento non valido.", status_code=422)
    opportunities = q.order_by(Opportunity.updated_at.desc(), Opportunity.id).all()
    if wanted_domain is not None:
        opportunities = [item for item in opportunities if wanted_domain in company_domains(item.company)]
    if needle:
        opportunities = [item for item in opportunities if _matches_text(item.company, needle)]
    if instagram_only:
        opportunities = [item for item in opportunities if effective_instagram_handle(item.company)]
    if category:
        category_key = normalize_category(category)
        opportunities = [item for item in opportunities if normalize_category(item.company.category) == category_key]
    if segment in ("refactor", "greenfield"):
        opportunities = [item for item in opportunities if (_has_website(item.company) == (segment == "refactor"))]
    if contactable is True:
        opportunities = [item for item in opportunities if is_contactable(item.company)]
    company_ids = [item.company_id for item in opportunities]
    scores = _latest_scores(session, company_ids)
    growth_scores = _latest_growth_scores(session, company_ids)
    if min_score is not None or priority:
        filtered: list[Opportunity] = []
        for item in opportunities:
            value, item_priority = _effective_score(item.company_id, scores, growth_scores)
            if min_score is not None and value < min_score:
                continue
            if priority and item_priority != priority:
                continue
            filtered.append(item)
        opportunities = filtered
    return _sorted_by_score(opportunities, scores, growth_scores)


def _like_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _matches_text(company: Company | None, needle: str) -> bool:
    """`q` trovato nel nome, nel dominio/URL del sito, nell'handle Instagram o nei link social."""
    if company is None:
        return False
    core = needle.lstrip("@") or needle
    name = (company.name or "").lower()
    if needle in name or core in name:
        return True
    if any(core in item for item in company_domains(company)):
        return True
    if company.website_url and core in company.website_url.lower():
        return True
    handle = effective_instagram_handle(company)
    if handle and core in handle:
        return True
    from app.services.pipeline_io import _social_links

    return any(core in item["url"].lower() for item in _social_links(company))


def normalize_domain(value: str | None) -> str | None:
    """"https://www.2-emme.com/chi-siamo" → "2-emme.com". None se non è un dominio."""
    text = (value or "").strip().lower()
    if not text:
        return None
    host = urlparse(text if "://" in text else f"http://{text}").hostname or ""
    host = host.rstrip(".").removeprefix("www.")
    if "." not in host or " " in host:
        return None
    return host


def company_domains(company: Company | None) -> set[str]:
    """Domini del sito dell'azienda (record Website e website_url), senza www."""
    if company is None:
        return set()
    found = {normalize_domain(website.domain) for website in company.websites}
    found.add(normalize_domain(company.website_url))
    return {item for item in found if item}


def dashboard(session: Session) -> dict:
    backfill_opportunities(session)
    rows = session.query(Opportunity.status, func.count(Opportunity.id)).group_by(Opportunity.status).all()
    counts = {name: 0 for name in CRM_STATUSES}
    counts.update({status: total for status, total in rows})
    favorites = session.query(func.count(Opportunity.id)).filter(Opportunity.is_favorite.is_(True)).scalar() or 0
    shortlisted = (
        session.query(func.count(Opportunity.id))
        .filter(or_(Opportunity.is_favorite.is_(True), Opportunity.status == "shortlisted"))
        .scalar()
        or 0
    )
    to_contact = counts.get("to_contact", 0)
    company_ids = [row[0] for row in session.query(Opportunity.company_id).all()]
    scores = _latest_scores(session, company_ids)
    growth_scores = _latest_growth_scores(session, company_ids)
    high_priority = sum(1 for score in scores.values() if score.priority in {"HIGH", "VERY_HIGH"})
    high_priority += sum(
        1
        for company_id, score in growth_scores.items()
        if company_id not in scores and score.priority in {"HIGH", "VERY_HIGH"}
    )
    return {
        "total": sum(counts.values()),
        "favorites": favorites,
        "shortlisted": shortlisted,
        "high_priority": high_priority,
        "to_contact": to_contact,
        "counts": counts,
    }


def get_opportunity(session: Session, opportunity_id: UUID) -> Opportunity | None:
    return (
        session.query(Opportunity)
        .options(
            selectinload(Opportunity.company).selectinload(Company.websites),
            selectinload(Opportunity.tag_links).selectinload(OpportunityTag.tag),
            selectinload(Opportunity.notes),
            selectinload(Opportunity.activities),
        )
        .filter(Opportunity.id == opportunity_id)
        .one_or_none()
    )


def get_opportunity_for_company(session: Session, company_id: UUID) -> Opportunity | None:
    company = session.get(Company, company_id)
    if company is None:
        return None
    opportunity = ensure_opportunity(session, company)
    session.commit()
    return get_opportunity(session, opportunity.id)


def update_opportunity(
    session: Session,
    opportunity_id: UUID,
    *,
    status: str | None = None,
    is_favorite: bool | None = None,
) -> Opportunity:
    opportunity = get_opportunity(session, opportunity_id)
    if opportunity is None:
        raise CrmServiceError("Opportunità non trovata.", status_code=404)
    if status is not None:
        if status not in CRM_STATUSES:
            raise CrmServiceError("Stato CRM non valido.", status_code=422)
        if status != opportunity.status:
            previous = opportunity.status
            opportunity.status = status
            session.add(
                Activity(
                    opportunity_id=opportunity.id,
                    type="status_change",
                    note=f"{previous} → {status}",
                    occurred_at=datetime.now(UTC),
                )
            )
    if is_favorite is not None:
        opportunity.is_favorite = is_favorite
    session.commit()
    loaded = get_opportunity(session, opportunity.id)
    assert loaded is not None
    return loaded


def add_note(session: Session, opportunity_id: UUID, body: str) -> Opportunity:
    opportunity = _require(session, opportunity_id)
    text = body.strip()
    if not text:
        raise CrmServiceError("La nota non può essere vuota.", status_code=422)
    session.add(OpportunityNote(opportunity_id=opportunity.id, body=text))
    session.commit()
    loaded = get_opportunity(session, opportunity.id)
    assert loaded is not None
    return loaded


def add_tag(session: Session, opportunity_id: UUID, name: str) -> Opportunity:
    opportunity = _require(session, opportunity_id)
    normalized = _normalize_tag(name)
    if not normalized:
        raise CrmServiceError("Il tag non può essere vuoto.", status_code=422)
    tag = session.query(Tag).filter_by(name=normalized).one_or_none()
    if tag is None:
        tag = Tag(name=normalized)
        session.add(tag)
        session.flush()
    existing = (
        session.query(OpportunityTag)
        .filter_by(opportunity_id=opportunity.id, tag_id=tag.id)
        .one_or_none()
    )
    if existing is None:
        session.add(OpportunityTag(opportunity_id=opportunity.id, tag_id=tag.id))
    session.commit()
    loaded = get_opportunity(session, opportunity.id)
    assert loaded is not None
    return loaded


def list_notes(session: Session, opportunity_id: UUID) -> list[OpportunityNote]:
    opportunity = _require(session, opportunity_id)
    return (
        session.query(OpportunityNote)
        .filter_by(opportunity_id=opportunity.id)
        .order_by(OpportunityNote.created_at.desc(), OpportunityNote.id)
        .all()
    )


def remove_tag(session: Session, opportunity_id: UUID, tag: UUID | str) -> Opportunity:
    """Toglie un solo tag dall'opportunità, indicato per id o per nome. Il tag resta nel catalogo."""
    opportunity = _require(session, opportunity_id)
    links = session.query(OpportunityTag).filter_by(opportunity_id=opportunity.id)
    link = None
    if isinstance(tag, UUID):
        link = links.filter_by(tag_id=tag).one_or_none()
    else:
        try:
            link = links.filter_by(tag_id=UUID(tag)).one_or_none()
        except ValueError:
            link = None
        if link is None:
            link = links.join(OpportunityTag.tag).filter(Tag.name == _normalize_tag(tag)).one_or_none()
    if link is None:
        raise CrmServiceError("Tag non trovato su questa opportunità.", status_code=404)
    session.delete(link)
    session.commit()
    loaded = get_opportunity(session, opportunity.id)
    assert loaded is not None
    return loaded


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def add_activity(
    session: Session,
    opportunity_id: UUID,
    *,
    activity_type: str,
    note: str | None,
    occurred_at: datetime | None,
    due_at: datetime | None = None,
) -> Opportunity:
    opportunity = _require(session, opportunity_id)
    if activity_type not in ACTIVITY_TYPES:
        raise CrmServiceError("Tipo attività non valido.", status_code=422)
    if due_at is not None:
        if activity_type not in SCHEDULED_ACTIVITY_TYPES:
            raise CrmServiceError("Questo tipo di attività non può essere pianificato.", status_code=422)
        session.add(
            Activity(
                opportunity_id=opportunity.id,
                type=activity_type,
                note=note.strip() if note else None,
                due_at=_as_utc(due_at),
            )
        )
    else:
        session.add(
            Activity(
                opportunity_id=opportunity.id,
                type=activity_type,
                note=note.strip() if note else None,
                occurred_at=occurred_at or datetime.now(UTC),
            )
        )
    session.commit()
    loaded = get_opportunity(session, opportunity.id)
    assert loaded is not None
    return loaded


def list_agenda(
    session: Session,
    *,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
    include_overdue: bool = True,
) -> list[Activity]:
    q = (
        session.query(Activity)
        .join(Opportunity)
        .join(Company)
        .options(
            selectinload(Activity.opportunity).selectinload(Opportunity.company),
        )
        .filter(Activity.due_at.isnot(None), Activity.completed_at.is_(None))
    )
    if from_dt is not None and to_dt is not None:
        if include_overdue:
            q = q.filter(Activity.due_at <= to_dt)
        else:
            q = q.filter(Activity.due_at >= from_dt, Activity.due_at <= to_dt)
    elif from_dt is not None:
        q = q.filter(Activity.due_at >= from_dt)
    elif to_dt is not None:
        q = q.filter(Activity.due_at <= to_dt)
    return q.order_by(Activity.due_at.asc()).all()


def list_agenda_history(
    session: Session,
    *,
    from_dt: datetime | None = None,
    to_dt: datetime | None = None,
    limit: int = 50,
) -> list[Activity]:
    q = (
        session.query(Activity)
        .join(Opportunity)
        .join(Company)
        .options(
            selectinload(Activity.opportunity).selectinload(Opportunity.company),
        )
        .filter(Activity.due_at.isnot(None), Activity.completed_at.isnot(None))
    )
    if from_dt is not None:
        q = q.filter(Activity.completed_at >= from_dt)
    if to_dt is not None:
        q = q.filter(Activity.completed_at <= to_dt)
    return q.order_by(Activity.completed_at.desc()).limit(limit).all()


def complete_activity(session: Session, activity_id: UUID) -> Activity:
    activity = (
        session.query(Activity)
        .options(
            selectinload(Activity.opportunity).selectinload(Opportunity.company),
        )
        .filter(Activity.id == activity_id)
        .one_or_none()
    )
    if activity is None:
        raise CrmServiceError("Attività non trovata.", status_code=404)
    if activity.due_at is None:
        raise CrmServiceError("L'attività non è pianificata.", status_code=422)
    if activity.completed_at is not None:
        raise CrmServiceError("Attività già completata.", status_code=422)
    now = datetime.now(UTC)
    activity.completed_at = now
    activity.occurred_at = now
    session.commit()
    session.refresh(activity)
    return activity


def reopen_activity(session: Session, activity_id: UUID) -> Activity:
    activity = (
        session.query(Activity)
        .options(
            selectinload(Activity.opportunity).selectinload(Opportunity.company),
        )
        .filter(Activity.id == activity_id)
        .one_or_none()
    )
    if activity is None:
        raise CrmServiceError("Attività non trovata.", status_code=404)
    if activity.due_at is None:
        raise CrmServiceError("L'attività non è pianificata.", status_code=422)
    if activity.completed_at is None:
        raise CrmServiceError("L'attività non è completata.", status_code=422)
    activity.completed_at = None
    activity.occurred_at = None
    session.commit()
    session.refresh(activity)
    return activity


def delete_scheduled_activity(session: Session, activity_id: UUID) -> None:
    activity = session.get(Activity, activity_id)
    if activity is None:
        raise CrmServiceError("Attività non trovata.", status_code=404)
    if activity.due_at is None:
        raise CrmServiceError("Solo le attività pianificate possono essere eliminate dall'agenda.", status_code=422)
    session.delete(activity)
    session.commit()


def latest_scores_map(session: Session, company_ids: list[UUID]) -> dict[UUID, OpportunityScore]:
    return _latest_scores(session, company_ids)


def latest_growth_scores_map(session: Session, company_ids: list[UUID]) -> dict[UUID, GrowthScore]:
    return _latest_growth_scores(session, company_ids)


def _require(session: Session, opportunity_id: UUID) -> Opportunity:
    opportunity = session.get(Opportunity, opportunity_id)
    if opportunity is None:
        raise CrmServiceError("Opportunità non trovata.", status_code=404)
    return opportunity


def _normalize_tag(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _latest_scores(session: Session, company_ids: list[UUID]) -> dict[UUID, OpportunityScore]:
    if not company_ids:
        return {}
    rows = (
        session.query(OpportunityScore)
        .filter(OpportunityScore.company_id.in_(company_ids))
        .order_by(OpportunityScore.created_at.desc())
        .all()
    )
    latest: dict[UUID, OpportunityScore] = {}
    for row in rows:
        if row.company_id is not None and row.company_id not in latest:
            latest[row.company_id] = row
    return latest


def _latest_growth_scores(session: Session, company_ids: list[UUID]) -> dict[UUID, GrowthScore]:
    if not company_ids:
        return {}
    rows = session.query(GrowthScore).filter(GrowthScore.company_id.in_(company_ids)).all()
    return {row.company_id: row for row in rows}


def _effective_score(
    company_id: UUID,
    scores: dict[UUID, OpportunityScore],
    growth_scores: dict[UUID, GrowthScore],
) -> tuple[int, str | None]:
    score = scores.get(company_id)
    if score is not None:
        return (score.opportunity_score, score.priority)
    growth = growth_scores.get(company_id)
    if growth is not None:
        return (growth.score, growth.priority)
    return (-1, None)


def _sorted_by_score(
    opportunities: list[Opportunity],
    scores: dict[UUID, OpportunityScore],
    growth_scores: dict[UUID, GrowthScore] | None = None,
) -> list[Opportunity]:
    growth_scores = growth_scores or {}

    def key(item: Opportunity) -> tuple[int, int, datetime, str]:
        value, _ = _effective_score(item.company_id, scores, growth_scores)
        # L'id chiude i pareggi (es. import in blocco con lo stesso updated_at): ordine totale e
        # stabile, necessario perché limit/offset non ripetano né saltino record.
        return (0 if item.is_favorite else 1, -value, item.updated_at, str(item.id))

    return sorted(opportunities, key=key)


def website_for(company: Company) -> Website | None:
    return company.websites[0] if company.websites else None


def _has_website(company: Company | None) -> bool:
    return bool(company and (company.website_url or company.websites))
