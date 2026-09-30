"""Company Research (Deep Research) e Business Signals per il secondo livello di approfondimento prospect.

Revision ID: 0019_company_research
Revises: 0018_sender_other_links
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0019_company_research"
down_revision: str | None = "0018_sender_other_links"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "company_research",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="never"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_label", sa.String(length=128), nullable=True),
        sa.Column("website_findings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("digital_presence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("social_signals", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("external_sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("brief", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("research_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id"),
    )
    op.create_index("ix_company_research_company_id", "company_research", ["company_id"])
    op.create_index("ix_company_research_status", "company_research", ["status"])
    op.alter_column("company_research", "status", server_default=None)
    op.alter_column("company_research", "progress_percent", server_default=None)

    op.create_table(
        "business_signals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("period", sa.String(length=16), nullable=False, server_default=""),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence", sa.String(length=16), nullable=False, server_default="unverified"),
        sa.Column("is_manual", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "key", "period", name="uq_business_signals_company_key_period"),
    )
    op.create_index("ix_business_signals_company_id", "business_signals", ["company_id"])
    op.alter_column("business_signals", "period", server_default=None)
    op.alter_column("business_signals", "confidence", server_default=None)
    op.alter_column("business_signals", "is_manual", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_business_signals_company_id", table_name="business_signals")
    op.drop_table("business_signals")
    op.drop_index("ix_company_research_status", table_name="company_research")
    op.drop_index("ix_company_research_company_id", table_name="company_research")
    op.drop_table("company_research")
