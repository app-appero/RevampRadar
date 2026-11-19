"""Schemi per l'inserimento CRM manuale e l'import con creazione."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.discovery import CompanyDetail, SocialLink


class HistoricalEventIn(BaseModel):
    external_ref: str = Field(min_length=1, max_length=255)
    kind: str = Field(min_length=1, max_length=32)
    channel: str = Field(min_length=1, max_length=32)
    sender: str | None = Field(default=None, max_length=255)
    recipient: str | None = Field(default=None, max_length=255)
    batch_id: str | None = Field(default=None, max_length=128)
    # Stringhe grezze: una data non va convertita in mezzanotte.
    occurred_at: str | None = None
    occurred_on: str | None = None


class ManualCompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    website_url: str | None = Field(default=None, max_length=2048)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    social_links: list[SocialLink] = Field(default_factory=list, max_length=12)
    instagram_handle: str | None = Field(
        default=None,
        max_length=255,
        description="Handle Instagram: «@nome», «nome» o URL del profilo. Salvato senza @, in minuscolo.",
        examples=["@albergomontecivetta"],
    )
    instagram_last_post_at: date | None = Field(
        default=None,
        description="Data dell'ultimo post Instagram visto (AAAA-MM-GG). Su un'azienda esistente vince la più recente.",
        examples=["2026-11-12"],
    )
    category: str | None = Field(default=None, max_length=128)
    city: str | None = Field(default=None, max_length=128)
    region: str | None = Field(default=None, max_length=128)
    province: str | None = Field(default=None, max_length=128)
    country: str | None = Field(default=None, max_length=64)
    source: str | None = Field(default=None, max_length=64)
    external_id: str | None = Field(default=None, max_length=128)
    status: str | None = None
    notes: list[str] = Field(default_factory=list, max_length=50)
    tags: list[str] = Field(default_factory=list, max_length=30)
    events: list[HistoricalEventIn] = Field(default_factory=list, max_length=20)


class CompanyImportRow(ManualCompanyCreate):
    name: str | None = Field(default=None, max_length=255)  # type: ignore[assignment]
    ref: str = Field(min_length=1, max_length=128)
    company_id: UUID | None = None


class CompanyImportRequest(BaseModel):
    create_missing: bool = False
    rows: list[CompanyImportRow] = Field(min_length=1, max_length=500)


class CompanyMatchCandidate(BaseModel):
    company_id: UUID
    opportunity_id: UUID | None
    name: str
    city: str | None
    region: str | None
    website_url: str | None
    email: str | None
    phone: str | None
    reasons: list[str]


class ManualCompanyResponse(BaseModel):
    outcome: Literal["created", "existing", "updated", "conflict"]
    company_id: UUID | None
    opportunity_id: UUID | None
    status: str | None
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)
    candidates: list[CompanyMatchCandidate] = Field(default_factory=list)
    company: CompanyDetail | None = None


class EventResult(BaseModel):
    external_ref: str
    outcome: Literal["recorded", "duplicate", "would_record", "invalid"]
    error: str | None = None


class ImportRowResult(BaseModel):
    ref: str
    outcome: Literal[
        "new",
        "created",
        "existing",
        "update",
        "updated",
        "ambiguous",
        "invalid",
        "id_not_found",
        "skipped",
    ]
    company_id: UUID | None = None
    opportunity_id: UUID | None = None
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)
    changes: list[str] = Field(default_factory=list)
    candidates: list[CompanyMatchCandidate] = Field(default_factory=list)
    events: list[EventResult] = Field(default_factory=list)


class CompanyImportResponse(BaseModel):
    create_missing: bool
    dry_run: bool
    rows: list[ImportRowResult]
