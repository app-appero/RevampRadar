"""Sender profile for email signature (site, freelance, socials).

Revision ID: 0009_sender_profile
Revises: 0008_audit_progress
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_sender_profile"
down_revision: str | None = "0008_audit_progress"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sender_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("intro", sa.Text(), nullable=False),
        sa.Column("website_url", sa.String(length=2048), nullable=False),
        sa.Column("freelancer_links", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("social_links", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("sender_profiles")
