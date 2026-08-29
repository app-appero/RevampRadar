"""Website and opportunity scores.

Revision ID: 0003_scores
Revises: 0002_website_audit
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_scores"
down_revision: str | None = "0002_website_audit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("audits", sa.Column("ai_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    op.create_table(
        "website_scores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("audit_id", sa.Uuid(), nullable=False),
        sa.Column("technical_score", sa.Integer(), nullable=False),
        sa.Column("performance_score", sa.Integer(), nullable=False),
        sa.Column("ui_score", sa.Integer(), nullable=True),
        sa.Column("ux_score", sa.Integer(), nullable=False),
        sa.Column("mobile_score", sa.Integer(), nullable=False),
        sa.Column("conversion_score", sa.Integer(), nullable=False),
        sa.Column("seo_score", sa.Integer(), nullable=False),
        sa.Column("trust_score", sa.Integer(), nullable=False),
        sa.Column("overall_score", sa.Integer(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("components", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("formula_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["audit_id"], ["audits.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_website_scores_audit_id", "website_scores", ["audit_id"], unique=True)

    op.create_table(
        "opportunity_scores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=True),
        sa.Column("audit_id", sa.Uuid(), nullable=False),
        sa.Column("website_score", sa.Integer(), nullable=False),
        sa.Column("business_score", sa.Integer(), nullable=False),
        sa.Column("opportunity_score", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("top_reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("positive_factors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("negative_factors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("recommended_service", sa.Text(), nullable=False),
        sa.Column("components", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("formula_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["audit_id"], ["audits.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_opportunity_scores_audit_id", "opportunity_scores", ["audit_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_opportunity_scores_audit_id", table_name="opportunity_scores")
    op.drop_table("opportunity_scores")
    op.drop_index("ix_website_scores_audit_id", table_name="website_scores")
    op.drop_table("website_scores")
    op.drop_column("audits", "ai_data")
