from uuid import UUID

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.crm import (
    CreateActivityRequest,
    CreateNoteRequest,
    CreateTagRequest,
    DashboardCounts,
    DashboardResponse,
    AgendaItemResponse,
    ActivityResponse,
    OpportunityDetail,
    OpportunitySummary,
    TagResponse,
    UpdateOpportunityRequest,
)
from app.services.crm_service import (
    CrmServiceError,
    add_activity,
    add_note,
    add_tag,
    complete_activity,
    dashboard,
    get_opportunity,
    get_opportunity_for_company,
    latest_scores_map,
    list_agenda,
    list_opportunities,
    remove_tag,
    update_opportunity,
    website_for,
)
from app.models.entities import Activity, Opportunity, OpportunityScore

router = APIRouter(tags=["crm"])


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
    q: str | None = None,
    category: str | None = None,
    city: str | None = None,
    tag: str | None = None,
    min_score: int | None = Query(default=None, ge=0, le=100),
    priority: str | None = None,
) -> list[OpportunitySummary]:
    try:
        items = list_opportunities(
            db,
            status=status,
            favorite=favorite,
            shortlist=shortlist,
            query=q,
            category=category,
            city=city,
            tag=tag,
            min_score=min_score,
            priority=priority,
        )
    except CrmServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    scores = latest_scores_map(db, [item.company_id for item in items])
    return [_summary(item, scores.get(item.company_id)) for item in items]


@router.get("/companies/{company_id}/opportunity", response_model=OpportunityDetail)
def get_company_opportunity(company_id: UUID, db: Session = Depends(get_db)) -> OpportunityDetail:
    opportunity = get_opportunity_for_company(db, company_id)
    if opportunity is None:
        raise HTTPException(status_code=404, detail="Azienda non trovata.")
    scores = latest_scores_map(db, [opportunity.company_id])
    return _detail(opportunity, scores.get(opportunity.company_id))


@router.get("/opportunities/{opportunity_id}", response_model=OpportunityDetail)
def get_opportunity_detail(opportunity_id: UUID, db: Session = Depends(get_db)) -> OpportunityDetail:
    opportunity = get_opportunity(db, opportunity_id)
    if opportunity is None:
        raise HTTPException(status_code=404, detail="Opportunità non trovata.")
    scores = latest_scores_map(db, [opportunity.company_id])
    return _detail(opportunity, scores.get(opportunity.company_id))


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
    scores = latest_scores_map(db, [opportunity.company_id])
    return _detail(opportunity, scores.get(opportunity.company_id))


@router.post("/opportunities/{opportunity_id}/notes", response_model=OpportunityDetail)
def post_note(
    opportunity_id: UUID,
    payload: CreateNoteRequest,
    db: Session = Depends(get_db),
) -> OpportunityDetail:
    try:
        opportunity = add_note(db, opportunity_id, payload.body)
    except CrmServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    scores = latest_scores_map(db, [opportunity.company_id])
    return _detail(opportunity, scores.get(opportunity.company_id))


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
    scores = latest_scores_map(db, [opportunity.company_id])
    return _detail(opportunity, scores.get(opportunity.company_id))


@router.delete("/opportunities/{opportunity_id}/tags/{tag_id}", response_model=OpportunityDetail)
def delete_tag(opportunity_id: UUID, tag_id: UUID, db: Session = Depends(get_db)) -> OpportunityDetail:
    try:
        opportunity = remove_tag(db, opportunity_id, tag_id)
    except CrmServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    scores = latest_scores_map(db, [opportunity.company_id])
    return _detail(opportunity, scores.get(opportunity.company_id))


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
    scores = latest_scores_map(db, [opportunity.company_id])
    return _detail(opportunity, scores.get(opportunity.company_id))


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _summary(opportunity: Opportunity, score: OpportunityScore | None) -> OpportunitySummary:
    company = opportunity.company
    website = website_for(company) if company else None
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
        status=opportunity.status,
        is_favorite=opportunity.is_favorite,
        tags=tags,
        website_score=score.website_score if score else None,
        opportunity_score=score.opportunity_score if score else None,
        priority=score.priority if score else None,
        latest_audit_id=score.audit_id if score else None,
        updated_at=opportunity.updated_at,
    )


def _detail(opportunity: Opportunity, score: OpportunityScore | None) -> OpportunityDetail:
    summary = _summary(opportunity, score)
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
    past.sort(
        key=lambda item: item.occurred_at or item.completed_at or item.created_at,
        reverse=True,
    )
    return pending + past


def _activity_response(item: Activity) -> ActivityResponse:
    return ActivityResponse(
        id=item.id,
        type=item.type,
        note=item.note,
        occurred_at=item.occurred_at,
        due_at=item.due_at,
        completed_at=item.completed_at,
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
