"""Company and discovery tables.

Revision ID: 0004_discovery
Revises: 0003_scores
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_discovery"
down_revision: str | None = "0003_scores"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=128), nullable=True),
        sa.Column("city", sa.String(length=128), nullable=True),
        sa.Column("region", sa.String(length=128), nullable=True),
        sa.Column("country", sa.String(length=64), nullable=True),
        sa.Column("website_url", sa.String(length=2048), nullable=True),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source", "external_id", name="uq_companies_source_external_id"),
    )
    op.create_index("ix_companies_name", "companies", ["name"])
    op.create_index("ix_companies_city", "companies", ["city"])

    op.create_foreign_key(
        "fk_websites_company_id",
        "websites",
        "companies",
        ["company_id"],
        ["id"],
    )
    op.create_index("ix_websites_company_id", "websites", ["company_id"])

    op.create_table(
        "discovery_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("industry", sa.String(length=128), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("max_results", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("total_found", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_discovery_runs_status", "discovery_runs", ["status"])

    op.create_table(
        "discovery_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("discovery_run_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.ForeignKeyConstraint(["discovery_run_id"], ["discovery_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("discovery_run_id", "company_id", name="uq_discovery_results_run_company"),
    )
    op.create_index("ix_discovery_results_discovery_run_id", "discovery_results", ["discovery_run_id"])
    op.create_index("ix_discovery_results_company_id", "discovery_results", ["company_id"])


def downgrade() -> None:
    op.drop_table("discovery_results")
    op.drop_table("discovery_runs")
    op.drop_index("ix_websites_company_id", table_name="websites")
    op.drop_constraint("fk_websites_company_id", "websites", type_="foreignkey")
    op.drop_table("companies")
