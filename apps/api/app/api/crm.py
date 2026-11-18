from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.entities import Activity, GrowthScore, Opportunity, OpportunityScore
from app.schemas.crm import (
    ActivityResponse,
    AgendaHistoryItemResponse,
    AgendaItemResponse,
    ContactStatusRequest,
    ContactStatusResponse,
    CreateActivityRequest,
    CreateNoteRequest,
    CreateTagRequest,
    DashboardCounts,
    DashboardResponse,
    OpportunityDetail,
    OpportunitySummary,
    TagResponse,
    UpdateOpportunityRequest,
)
from app.services.contact_status import contact_status
from app.services.crm_service import (
    CrmServiceError,
    add_activity,
    add_note,
    add_tag,
    complete_activity,
    dashboard,
    delete_scheduled_activity,
    get_opportunity,
    get_opportunity_for_company,
    latest_growth_scores_map,
    latest_scores_map,
    list_agenda,
    list_agenda_history,
    list_opportunities,
    normalize_category,
    remove_tag,
    reopen_activity,
    update_opportunity,
    website_for,
)
from app.services.pipeline_io import PipelineImportError, build_export, import_export

router = APIRouter(tags=["crm"])

_Q_DESCRIPTION = "Testo cercato nel nome dell'azienda (senza distinzione maiuscole/minuscole)."
_SEARCH_DESCRIPTION = "Alias di `q`, stesso comportamento. Se sono presenti entrambi vale `q`."


def _text_query(q: str | None, search: str | None) -> str | None:
    """`search` è un alias di `q`: prima veniva ignorato in silenzio."""
    for value in (q, search):
        if value is not None and value.strip():
            return value
    return None


@router.get("/agenda/history", response_model=list[AgendaHistoryItemResponse])
def get_agenda_history(
    db: Session = Depends(get_db),
    from_dt: datetime | None = Query(default=None, alias="from"),
    to_dt: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[AgendaHistoryItemResponse]:
    items = list_agenda_history(db, from_dt=from_dt, to_dt=to_dt, limit=limit)
    return [_agenda_history_item(item) for item in items]


@router.get("/agenda", response_model=list[AgendaItemResponse])
def get_agenda(
    db: Session = Depends(get_db),
    from_dt: datetime | None = Query(default=None, alias="from"),
    to_dt: datetime | None = Query(default=None, alias="to"),
    include_overdue: bool = True,
) -> list[AgendaItemResponse]:
    now = datetime.now(UTC)
    items = list_agenda(db, from_dt=from_dt, to_dt=to_dt, include_overdue=include_overdue)
    return [_agenda_item(item, now) for item in items]


@router.post("/activities/{activity_id}/complete", response_model=ActivityResponse)
def post_complete_activity(activity_id: UUID, db: Session = Depends(get_db)) -> ActivityResponse:
    try:
        activity = complete_activity(db, activity_id)
    except CrmServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return _activity_response(activity)


@router.post("/activities/{activity_id}/reopen", response_model=ActivityResponse)
def post_reopen_activity(activity_id: UUID, db: Session = Depends(get_db)) -> ActivityResponse:
    try:
        activity = reopen_activity(db, activity_id)
    except CrmServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return _activity_response(activity)


@router.delete("/activities/{activity_id}", status_code=204)
def delete_activity(activity_id: UUID, db: Session = Depends(get_db)) -> Response:
    try:
        delete_scheduled_activity(db, activity_id)
    except CrmServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    return Response(status_code=204)


@router.get("/opportunities/dashboard", response_model=DashboardResponse)
def get_dashboard(db: Session = Depends(get_db)) -> DashboardResponse:
    data = dashboard(db)
    return DashboardResponse(
        total=data["total"],
        favorites=data["favorites"],
        shortlisted=data["shortlisted"],
        high_priority=data["high_priority"],
        to_contact=data["to_contact"],
        counts=DashboardCounts(**data["counts"]),
    )


@router.get("/opportunities", response_model=list[OpportunitySummary])
def get_opportunities(
    db: Session = Depends(get_db),
    status: str | None = None,
    favorite: bool | None = None,
    shortlist: bool = False,
    q: str | None = Query(default=None, description=_Q_DESCRIPTION),
    search: str | None = Query(default=None, description=_SEARCH_DESCRIPTION),
    category: str | None = None,
    city: str | None = None,
    tag: str | None = None,
    min_score: int | None = Query(default=None, ge=0, le=100),
    priority: str | None = None,
    segment: str | None = None,
    contactable: bool | None = None,
) -> list[OpportunitySummary]:
    try:
        items = list_opportunities(
            db,
            status=status,
            favorite=favorite,
            shortlist=shortlist,
            query=_text_query(q, search),
            category=category,
            city=city,
            tag=tag,
            min_score=min_score,
            priority=priority,
            segment=segment,
            contactable=contactable,
        )
    except CrmServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    scores, growth_scores = _score_maps(db, [item.company_id for item in items])
    return [_summary(item, scores.get(item.company_id), growth_scores.get(item.company_id)) for item in items]


@router.get("/opportunities/export")
def export_opportunities(
    db: Session = Depends(get_db),
    status: str | None = None,
    favorite: bool | None = None,
    shortlist: bool = False,
    q: str | None = Query(default=None, description=_Q_DESCRIPTION),
    search: str | None = Query(default=None, description=_SEARCH_DESCRIPTION),
    category: str | None = None,
    city: str | None = None,
    tag: str | None = None,
    min_score: int | None = Query(default=None, ge=0, le=100),
    priority: str | None = None,
    segment: str | None = None,
    contactable: bool | None = None,
) -> dict[str, Any]:
    """JSON completo delle aziende che rispettano i filtri correnti della Pipeline."""
    try:
        return build_export(
            db,
            status=status,
            favorite=favorite,
            shortlist=shortlist,
            query=_text_query(q, search),
            category=category,
            city=city,
            tag=tag,
            min_score=min_score,
            priority=priority,
            segment=segment,
            contactable=contactable,
        )
    except CrmServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/opportunities/import")
def import_opportunities(payload: Any = Body(...), db: Session = Depends(get_db)) -> dict[str, Any]:
    """Reimporta il JSON arricchito aggiornando le aziende indicate (mai in modo distruttivo)."""
    try:
        return import_export(db, payload)
    except PipelineImportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post(
    "/opportunities/contact-status",
    response_model=ContactStatusResponse,
    summary="Stato di contatto per una lista di email",
    description=(
        "Controllo prima di inviare bozze esterne (es. Aruba): per ogni email indica se l'azienda "
        "collegata risulta già contattata (stato contacted o successivo, invio registrato o tag di "
        "invio come lotto2-20261116-inviato), con stato CRM e data dell'ultimo contatto. "
        "Sola lettura: non modifica dati e non invia messaggi."
    ),
)
def post_contact_status(payload: ContactStatusRequest, db: Session = Depends(get_db)) -> ContactStatusResponse:
    return ContactStatusResponse(**contact_status(db, payload.emails, payload.contacted_tags))


@router.get("/opportunities/categories")
def get_opportunity_categories(
    db: Session = Depends(get_db),
    status: str | None = None,
    favorite: bool | None = None,
    shortlist: bool = False,
    q: str | None = Query(default=None, description=_Q_DESCRIPTION),
    search: str | None = Query(default=None, description=_SEARCH_DESCRIPTION),
    city: str | None = None,
    tag: str | None = None,
    min_score: int | None = Query(default=None, ge=0, le=100),
    priority: str | None = None,
    segment: str | None = None,
    contactable: bool | None = None,
) -> list[dict]:
    # La faccetta applica tutti i filtri tranne il settore stesso.
    items = get_opportunities(
        db=db, status=status, favorite=favorite, shortlist=shortlist, q=_text_query(q, search), search=None,
        category=None, city=city, tag=tag, min_score=min_score, priority=priority,
        segment=segment, contactable=contactable,
    )
    counts: dict[str, int] = {}
    variants: dict[str, set[str]] = {}
    for item in items:
        key = normalize_category(item.category)
        if key:
            counts[key] = counts.get(key, 0) + 1
            variants.setdefault(key, set()).add(item.category)
    return [
        {"value": key, "label": key.capitalize(), "count": counts[key], "variants": sorted(variants[key])}
        for key in sorted(counts)
    ]


@router.get("/companies/{company_id}/opportunity", response_model=OpportunityDetail)
def get_company_opportunity(company_id: UUID, db: Session = Depends(get_db)) -> OpportunityDetail:
    opportunity = get_opportunity_for_company(db, company_id)
    if opportunity is None:
        raise HTTPException(status_code=404, detail="Azienda non trovata.")
    scores, growth_scores = _score_maps(db, [opportunity.company_id])
    return _detail(opportunity, scores.get(opportunity.company_id), growth_scores.get(opportunity.company_id))


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityDetail)
def get_opportunity_detail(opportunity_id: UUID, db: Session = Depends(get_db)) -> OpportunityDetail:
    opportunity = get_opportunity(db, opportunity_id)
    if opportunity is None:
        raise HTTPException(status_code=404, detail="Opportunità non trovata.")
    scores, growth_scores = _score_maps(db, [opportunity.company_id])
    return _detail(opportunity, scores.get(opportunity.company_id), growth_scores.get(opportunity.company_id))


@router.patch("/opportunities/{opportunity_id}", response_model=OpportunityDetail)
def patch_opportunity(
    opportunity_id: UUID,
    payload: UpdateOpportunityRequest,
    db: Session = Depends(get_db),
) -> OpportunityDetail:
    try:
        opportunity = update_opportunity(
            db,
            opportunity_id,
            status=payload.status,
            is_favorite=payload.is_favorite,
        )
    except CrmServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    scores, growth_scores = _score_maps(db, [opportunity.company_id])
    return _detail(opportunity, scores.get(opportunity.company_id), growth_scores.get(opportunity.company_id))


@router.post(
    "/opportunities/{opportunity_id}/notes",
    response_model=OpportunityDetail,
    summary="Aggiunge una nota all'opportunità",
    description=(
        'Corpo JSON: `{"body": "testo della nota"}`. Il campo si chiama **body**: '
        "`content`, `text` o `note` vengono rifiutati con 422 e un messaggio che indica il campo corretto."
    ),
)
def post_note(
    opportunity_id: UUID,
    payload: CreateNoteRequest,
    db: Session = Depends(get_db),
) -> OpportunityDetail:
    try:
        opportunity = add_note(db, opportunity_id, payload.body)
    except CrmServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    scores, growth_scores = _score_maps(db, [opportunity.company_id])
    return _detail(opportunity, scores.get(opportunity.company_id), growth_scores.get(opportunity.company_id))


@router.post("/opportunities/{opportunity_id}/tags", response_model=OpportunityDetail)
def post_tag(
    opportunity_id: UUID,
    payload: CreateTagRequest,
    db: Session = Depends(get_db),
) -> OpportunityDetail:
    try:
        opportunity = add_tag(db, opportunity_id, payload.name)
    except CrmServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    scores, growth_scores = _score_maps(db, [opportunity.company_id])
    return _detail(opportunity, scores.get(opportunity.company_id), growth_scores.get(opportunity.company_id))


@router.delete("/opportunities/{opportunity_id}/tags/{tag_id}", response_model=OpportunityDetail)
def delete_tag(opportunity_id: UUID, tag_id: UUID, db: Session = Depends(get_db)) -> OpportunityDetail:
    try:
        opportunity = remove_tag(db, opportunity_id, tag_id)
    except CrmServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    scores, growth_scores = _score_maps(db, [opportunity.company_id])
    return _detail(opportunity, scores.get(opportunity.company_id), growth_scores.get(opportunity.company_id))


@router.post("/opportunities/{opportunity_id}/activities", response_model=OpportunityDetail)
def post_activity(
    opportunity_id: UUID,
    payload: CreateActivityRequest,
    db: Session = Depends(get_db),
) -> OpportunityDetail:
    try:
        opportunity = add_activity(
            db,
            opportunity_id,
            activity_type=payload.type,
            note=payload.note,
            occurred_at=payload.occurred_at,
            due_at=payload.due_at,
        )
    except CrmServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    scores, growth_scores = _score_maps(db, [opportunity.company_id])
    return _detail(opportunity, scores.get(opportunity.company_id), growth_scores.get(opportunity.company_id))


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _score_maps(
    db: Session, company_ids: list[UUID]
) -> tuple[dict[UUID, OpportunityScore], dict[UUID, GrowthScore]]:
    return latest_scores_map(db, company_ids), latest_growth_scores_map(db, company_ids)


def _summary(
    opportunity: Opportunity,
    score: OpportunityScore | None,
    growth: GrowthScore | None = None,
) -> OpportunitySummary:
    company = opportunity.company
    website = website_for(company) if company else None
    has_website = bool(company and (company.website_url or company.websites))
    tags = [
        TagResponse(id=link.tag.id, name=link.tag.name)
        for link in opportunity.tag_links
        if link.tag is not None
    ]
    tags.sort(key=lambda item: item.name)
    return OpportunitySummary(
        id=opportunity.id,
        company_id=opportunity.company_id,
        company_name=company.name if company else "",
        category=company.category if company else None,
        city=company.city if company else None,
        region=company.region if company else None,
        website_url=(company.website_url if company else None) or (website.normalized_url if website else None),
        domain=website.domain if website else None,
        places_checked_at=company.places_checked_at if company else None,
        has_email=bool(company and company.email),
        has_phone=bool(company and company.phone),
        status=opportunity.status,
        is_favorite=opportunity.is_favorite,
        tags=tags,
        website_score=score.website_score if score else None,
        opportunity_score=score.opportunity_score if score else None,
        priority=score.priority if score else None,
        latest_audit_id=score.audit_id if score else None,
        has_website=has_website,
        growth_score=growth.score if growth else None,
        growth_priority=growth.priority if growth else None,
        segment="refactor" if has_website else "greenfield",
        updated_at=opportunity.updated_at,
    )


def _detail(
    opportunity: Opportunity,
    score: OpportunityScore | None,
    growth: GrowthScore | None = None,
) -> OpportunityDetail:
    summary = _summary(opportunity, score, growth)
    notes = sorted(opportunity.notes, key=lambda item: item.created_at, reverse=True)
    activities = _sorted_activities(opportunity.activities)
    return OpportunityDetail(
        **summary.model_dump(),
        notes=[{"id": item.id, "body": item.body, "created_at": item.created_at} for item in notes],
        activities=[_activity_response(item) for item in activities],
    )


def _sorted_activities(activities: list[Activity]) -> list[Activity]:
    pending = [item for item in activities if item.due_at is not None and item.completed_at is None]
    past = [item for item in activities if not (item.due_at is not None and item.completed_at is None)]
    pending.sort(key=lambda item: item.due_at or datetime.min.replace(tzinfo=UTC))
    past.sort(key=_activity_moment, reverse=True)
    return pending + past


def _activity_moment(item: Activity) -> datetime:
    """Ordina gli eventi. La mezzanotte resta solo una chiave in memoria, non un orario salvato."""
    if item.occurred_at is not None:
        return item.occurred_at
    if item.occurred_on is not None:
        return datetime.combine(item.occurred_on, datetime.min.time(), tzinfo=UTC)
    if item.completed_at is not None:
        return item.completed_at
    return item.created_at


def _activity_response(item: Activity) -> ActivityResponse:
    return ActivityResponse(
        id=item.id,
        type=item.type,
        note=item.note,
        occurred_at=item.occurred_at,
        occurred_on=item.occurred_on,
        due_at=item.due_at,
        completed_at=item.completed_at,
        channel=item.channel,
        sender=item.sender,
        recipient=item.recipient,
        batch_id=item.batch_id,
        external_ref=item.external_ref,
        created_at=item.created_at,
    )


def _agenda_item(activity: Activity, now: datetime) -> AgendaItemResponse:
    opportunity = activity.opportunity
    company = opportunity.company if opportunity else None
    if activity.due_at is None:
        raise ValueError("Agenda item requires due_at")
    return AgendaItemResponse(
        id=activity.id,
        opportunity_id=activity.opportunity_id,
        company_id=opportunity.company_id if opportunity else activity.opportunity_id,
        company_name=company.name if company else "",
        type=activity.type,
        note=activity.note,
        due_at=activity.due_at,
        created_at=activity.created_at,
        is_overdue=_as_utc(activity.due_at) < _as_utc(now),
    )


def _agenda_history_item(activity: Activity) -> AgendaHistoryItemResponse:
    opportunity = activity.opportunity
    company = opportunity.company if opportunity else None
    if activity.due_at is None or activity.completed_at is None:
        raise ValueError("History item requires due_at and completed_at")
    return AgendaHistoryItemResponse(
        id=activity.id,
        opportunity_id=activity.opportunity_id,
        company_id=opportunity.company_id if opportunity else activity.opportunity_id,
        company_name=company.name if company else "",
        type=activity.type,
        note=activity.note,
        due_at=activity.due_at,
        completed_at=activity.completed_at,
        created_at=activity.created_at,
    )
