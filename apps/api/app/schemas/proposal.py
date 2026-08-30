from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ProblemItem(BaseModel):
    code: str
    severity: str
    title: str
    recommendation: str


class ProposalResponse(BaseModel):
    id: UUID
    audit_id: UUID
    company_id: UUID | None
    source: str
    prompt_version: str
    summary: str
    priority_problems: list[ProblemItem]
    recommended_service: str
    strategy: str
    email_subject: str
    email_body: str
    brief: str
    range_min: int
    range_max: int
    currency: str
    range_note: str
    created_at: datetime
    updated_at: datetime
