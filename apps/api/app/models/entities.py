from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.models.base import Base

JsonType = JSONB().with_variant(JSON, "sqlite")


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_companies_source_external_id"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str | None] = mapped_column(String(128), nullable=True)
    city: Mapped[str | None] = mapped_column(String(128), nullable=True)
    region: Mapped[str | None] = mapped_column(String(128), nullable=True)
    country: Mapped[str | None] = mapped_column(String(64), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="discovered", nullable=False)
    extra: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    websites: Mapped[list["Website"]] = relationship(back_populates="company")
    discovery_results: Mapped[list["DiscoveryResult"]] = relationship(back_populates="company")
    opportunity: Mapped["Opportunity | None"] = relationship(
        back_populates="company", uselist=False, cascade="all, delete-orphan"
    )


class Website(Base):
    __tablename__ = "websites"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    company_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("companies.id"), nullable=True, index=True
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    normalized_url: Mapped[str] = mapped_column(String(2048), unique=True, index=True, nullable=False)
    domain: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    company: Mapped[Company | None] = relationship(back_populates="websites")
    audits: Mapped[list["Audit"]] = relationship(back_populates="website")


class Audit(Base):
    __tablename__ = "audits"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    website_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("websites.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)
    request_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scanner_version: Mapped[str] = mapped_column(String(32), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    http_data: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    html_data: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    seo_data: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    performance_data: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    ai_data: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    website: Mapped[Website] = relationship(back_populates="audits")
    findings: Mapped[list["AuditFinding"]] = relationship(
        back_populates="audit", cascade="all, delete-orphan"
    )
    screenshots: Mapped[list["Screenshot"]] = relationship(
        back_populates="audit", cascade="all, delete-orphan"
    )
    website_score: Mapped["WebsiteScore | None"] = relationship(
        back_populates="audit", cascade="all, delete-orphan", uselist=False
    )
    opportunity_score: Mapped["OpportunityScore | None"] = relationship(
        back_populates="audit", cascade="all, delete-orphan", uselist=False
    )
    proposal: Mapped["Proposal | None"] = relationship(
        back_populates="audit", cascade="all, delete-orphan", uselist=False
    )


class AuditFinding(Base):
    __tablename__ = "audit_findings"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    audit_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("audits.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), default="scanner", nullable=False)

    audit: Mapped[Audit] = relationship(back_populates="findings")


class Screenshot(Base):
    __tablename__ = "screenshots"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    audit_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("audits.id"), nullable=False, index=True)
    device: Mapped[str] = mapped_column(String(32), nullable=False)
    viewport_width: Mapped[int] = mapped_column(nullable=False)
    viewport_height: Mapped[int] = mapped_column(nullable=False)
    file_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    audit: Mapped[Audit] = relationship(back_populates="screenshots")


class WebsiteScore(Base):
    __tablename__ = "website_scores"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    audit_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("audits.id"), unique=True, nullable=False, index=True
    )
    technical_score: Mapped[int] = mapped_column(Integer, nullable=False)
    performance_score: Mapped[int] = mapped_column(Integer, nullable=False)
    ui_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ux_score: Mapped[int] = mapped_column(Integer, nullable=False)
    mobile_score: Mapped[int] = mapped_column(Integer, nullable=False)
    conversion_score: Mapped[int] = mapped_column(Integer, nullable=False)
    seo_score: Mapped[int] = mapped_column(Integer, nullable=False)
    trust_score: Mapped[int] = mapped_column(Integer, nullable=False)
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    components: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    formula_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    audit: Mapped[Audit] = relationship(back_populates="website_score")


class OpportunityScore(Base):
    __tablename__ = "opportunity_scores"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    company_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("companies.id"), nullable=True, index=True
    )
    audit_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("audits.id"), unique=True, nullable=False, index=True
    )
    website_score: Mapped[int] = mapped_column(Integer, nullable=False)
    business_score: Mapped[int] = mapped_column(Integer, nullable=False)
    opportunity_score: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    top_reasons: Mapped[list] = mapped_column(JsonType, nullable=False)
    positive_factors: Mapped[list] = mapped_column(JsonType, nullable=False)
    negative_factors: Mapped[list] = mapped_column(JsonType, nullable=False)
    recommended_service: Mapped[str] = mapped_column(Text, nullable=False)
    components: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    formula_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    audit: Mapped[Audit] = relationship(back_populates="opportunity_score")


class DiscoveryRun(Base):
    __tablename__ = "discovery_runs"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    industry: Mapped[str] = mapped_column(String(128), nullable=False)
    location: Mapped[str] = mapped_column(String(255), nullable=False)
    max_results: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)
    total_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    results: Mapped[list["DiscoveryResult"]] = relationship(
        back_populates="discovery_run", cascade="all, delete-orphan"
    )
    bulk_scans: Mapped[list["BulkScan"]] = relationship(
        back_populates="discovery_run"
    )


class DiscoveryResult(Base):
    __tablename__ = "discovery_results"
    __table_args__ = (
        UniqueConstraint("discovery_run_id", "company_id", name="uq_discovery_results_run_company"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    discovery_run_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("discovery_runs.id"), nullable=False, index=True
    )
    company_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("companies.id"), nullable=False, index=True)

    discovery_run: Mapped[DiscoveryRun] = relationship(back_populates="results")
    company: Mapped[Company] = relationship(back_populates="discovery_results")


class BulkScan(Base):
    __tablename__ = "bulk_scans"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    discovery_run_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("discovery_runs.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    concurrency: Mapped[int] = mapped_column(Integer, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    discovery_run: Mapped[DiscoveryRun] = relationship(back_populates="bulk_scans")
    items: Mapped[list["BulkScanItem"]] = relationship(
        back_populates="bulk_scan", cascade="all, delete-orphan"
    )


class BulkScanItem(Base):
    __tablename__ = "bulk_scan_items"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    bulk_scan_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("bulk_scans.id"), nullable=False, index=True
    )
    company_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("companies.id"), nullable=False, index=True)
    audit_id: Mapped[UUID | None] = mapped_column(Uuid, ForeignKey("audits.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    bulk_scan: Mapped[BulkScan] = relationship(back_populates="items")
    company: Mapped[Company] = relationship()
    audit: Mapped[Audit | None] = relationship()


class Opportunity(Base):
    __tablename__ = "opportunities"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    company_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("companies.id"), unique=True, nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="discovered", nullable=False, index=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    company: Mapped[Company] = relationship(back_populates="opportunity")
    notes: Mapped[list["OpportunityNote"]] = relationship(
        back_populates="opportunity", cascade="all, delete-orphan"
    )
    activities: Mapped[list["Activity"]] = relationship(
        back_populates="opportunity", cascade="all, delete-orphan"
    )
    tag_links: Mapped[list["OpportunityTag"]] = relationship(
        back_populates="opportunity", cascade="all, delete-orphan"
    )


class OpportunityNote(Base):
    __tablename__ = "opportunity_notes"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    opportunity_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("opportunities.id"), nullable=False, index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    opportunity: Mapped[Opportunity] = relationship(back_populates="notes")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    links: Mapped[list["OpportunityTag"]] = relationship(
        back_populates="tag", cascade="all, delete-orphan"
    )


class OpportunityTag(Base):
    __tablename__ = "opportunity_tags"
    __table_args__ = (UniqueConstraint("opportunity_id", "tag_id", name="uq_opportunity_tags"),)

    opportunity_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("opportunities.id"), primary_key=True
    )
    tag_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("tags.id"), primary_key=True)

    opportunity: Mapped[Opportunity] = relationship(back_populates="tag_links")
    tag: Mapped[Tag] = relationship(back_populates="links")


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    opportunity_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("opportunities.id"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    opportunity: Mapped[Opportunity] = relationship(back_populates="activities")


class Proposal(Base):
    __tablename__ = "proposals"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    audit_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("audits.id"), unique=True, nullable=False, index=True
    )
    company_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("companies.id"), nullable=True, index=True
    )
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    priority_problems: Mapped[list] = mapped_column(JsonType, nullable=False)
    recommended_service: Mapped[str] = mapped_column(Text, nullable=False)
    strategy: Mapped[str] = mapped_column(Text, nullable=False)
    email_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    email_body: Mapped[str] = mapped_column(Text, nullable=False)
    brief: Mapped[str] = mapped_column(Text, nullable=False)
    range_min: Mapped[int] = mapped_column(Integer, nullable=False)
    range_max: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="EUR", nullable=False)
    range_note: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    audit: Mapped[Audit] = relationship(back_populates="proposal")
    company: Mapped[Company | None] = relationship()
