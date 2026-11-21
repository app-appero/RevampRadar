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
    allow_duplicates: bool = Field(
        default=False,
        description=(
            "Solo POST /companies. Con false (default) un'azienda con stesso handle Instagram, dominio del "
            "sito (o stessa pagina su host condivisi) o email già presente è rifiutata con 409 e l'id "
            "esistente. true = crea comunque (es. sede diversa con email centrale), con la deduplica normale."
        ),
    )


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
    outcome: Literal["created", "existing", "updated", "conflict", "duplicate"]
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


class InstagramImportItem(BaseModel):
    instagram: str = Field(min_length=1, max_length=255, description="«@nome», «nome» o URL del profilo.")
    name: str | None = Field(default=None, max_length=255, description="Nome attività; assente = l'handle.")
    city: str | None = Field(default=None, max_length=128)
    province: str | None = Field(default=None, max_length=128)
    region: str | None = Field(default=None, max_length=128)
    category: str | None = Field(default=None, max_length=128)
    instagram_last_post_at: date | None = None
    notes: list[str] = Field(default_factory=list, max_length=20)
    tags: list[str] = Field(default_factory=list, max_length=20)


class InstagramImportDefaults(BaseModel):
    city: str | None = Field(default=None, max_length=128)
    province: str | None = Field(default=None, max_length=128)
    region: str | None = Field(default=None, max_length=128)
    category: str | None = Field(default=None, max_length=128)
    status: str | None = None
    source: str = Field(default="instagram_import", max_length=64)
    tags: list[str] = Field(default_factory=list, max_length=20)
    notes: list[str] = Field(default_factory=list, max_length=20)


class InstagramImportRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "items": ["@fioridilia", "https://www.instagram.com/panificio.alforno/",
                              {"instagram": "dolce.tv", "name": "Pasticceria Dolce", "city": "Treviso"}],
                    "defaults": {"province": "Treviso", "tags": ["ricerca-ig-20261121"]},
                }
            ]
        }
    }

    items: list[str | InstagramImportItem] = Field(min_length=1, max_length=200)
    defaults: InstagramImportDefaults = Field(default_factory=InstagramImportDefaults)
    dry_run: bool = Field(default=False, description="true = solo anteprima, nessuna scheda creata.")


class InstagramImportRow(BaseModel):
    input: str
    instagram_handle: str | None = None
    outcome: Literal["created", "would_create", "duplicate", "invalid", "conflict"]
    company_id: UUID | None = None
    opportunity_id: UUID | None = None
    reasons: list[str] = Field(default_factory=list)
    error: str | None = None


class InstagramImportResponse(BaseModel):
    dry_run: bool
    created: int
    duplicates: int
    invalid: int
    rows: list[InstagramImportRow]


class CompanyMatchReason(BaseModel):
    signal: str = Field(
        description=(
            "instagram_handle, email, domain, website_url, phone, instagram_matches_name, domain_matches_name, "
            "name_exact, name_matches_instagram, name_matches_domain, name_similar, same_city, other_city"
        )
    )
    detail: str
    points: int


class CompanyMatchItem(BaseModel):
    company_id: UUID
    opportunity_id: UUID | None
    name: str
    city: str | None
    status: str | None
    instagram_handle: str | None
    domains: list[str]
    email: str | None
    phone: str | None
    score: int = Field(description="0-100.")
    strength: Literal["strong", "probable", "weak"] = Field(description="strong ≥ 85, probable ≥ 65, weak ≥ 50.")
    reasons: list[CompanyMatchReason]


class CompanyMatchResponse(BaseModel):
    normalized: dict[str, str | None]
    matches: list[CompanyMatchItem]

