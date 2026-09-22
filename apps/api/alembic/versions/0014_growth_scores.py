"""Growth score for companies without a website, and greenfield proposals.

Revision ID: 0014_growth_scores
Revises: 0013_activity_schedule
Create Date: 2026-09-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0014_growth_scores"
down_revision: str | None = "0013_activity_schedule"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "growth_scores",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("top_reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("positive_factors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("negative_factors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("recommended_service", sa.Text(), nullable=False),
        sa.Column("components", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("peer_sample_size", sa.Integer(), nullable=False),
        sa.Column("formula_version", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id"),
    )
    op.create_index("ix_growth_scores_company_id", "growth_scores", ["company_id"])

    op.add_column("proposals", sa.Column("kind", sa.String(length=16), nullable=False, server_default="refactor"))
    op.alter_column("proposals", "kind", server_default=None)
    op.alter_column("proposals", "audit_id", existing_type=sa.Uuid(), nullable=True)


def downgrade() -> None:
    op.alter_column("proposals", "audit_id", existing_type=sa.Uuid(), nullable=False)
    op.drop_column("proposals", "kind")
    op.drop_index("ix_growth_scores_company_id", table_name="growth_scores")
    op.drop_table("growth_scores")
