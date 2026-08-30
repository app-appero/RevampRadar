from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


CRM_STATUSES = (
    "discovered",
    "analyzed",
    "qualified",
    "shortlisted",
    "to_contact",
    "contacted",
    "replied",
    "meeting",
    "proposal",
    "won",
    "lost",
)

ACTIVITY_TYPES = ("note", "status_change", "call", "email", "meeting", "other")


class TagResponse(BaseModel):
    id: UUID
    name: str


class NoteResponse(BaseModel):
    id: UUID
    body: str
    created_at: datetime


class ActivityResponse(BaseModel):
    id: UUID
    type: str
    note: str | None
    occurred_at: datetime
    created_at: datetime


class OpportunitySummary(BaseModel):
    id: UUID
    company_id: UUID
    company_name: str
    category: str | None
    city: str | None
    region: str | None
    website_url: str | None
    domain: str | None
    status: str
    is_favorite: bool
    tags: list[TagResponse]
    website_score: int | None = None
    opportunity_score: int | None = None
    priority: str | None = None
    latest_audit_id: UUID | None = None
    updated_at: datetime


class OpportunityDetail(OpportunitySummary):
    notes: list[NoteResponse]
    activities: list[ActivityResponse]


class DashboardCounts(BaseModel):
    discovered: int = 0
    analyzed: int = 0
    qualified: int = 0
    shortlisted: int = 0
    to_contact: int = 0
    contacted: int = 0
    replied: int = 0
    meeting: int = 0
    proposal: int = 0
    won: int = 0
    lost: int = 0


class DashboardResponse(BaseModel):
    total: int
    favorites: int
    shortlisted: int
    high_priority: int
    to_contact: int
    counts: DashboardCounts


class UpdateOpportunityRequest(BaseModel):
    status: str | None = None
    is_favorite: bool | None = None


class CreateNoteRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class CreateTagRequest(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class CreateActivityRequest(BaseModel):
    type: str
    note: str | None = Field(default=None, max_length=2000)
    occurred_at: datetime | None = None
