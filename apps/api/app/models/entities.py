from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, Uuid

from app.models.base import Base

JsonType = JSONB().with_variant(JSON, "sqlite")


class Website(Base):
    __tablename__ = "websites"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    company_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
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
