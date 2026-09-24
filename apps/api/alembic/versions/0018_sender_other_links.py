"""Sender profile: separate "other links" from social links (e.g. GitHub).

Revision ID: 0018_sender_other_links
Revises: 0017_ai_credentials
Create Date: 2026-09-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018_sender_other_links"
down_revision: str | None = "0017_ai_credentials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sender_profiles",
        sa.Column(
            "other_links",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.alter_column("sender_profiles", "other_links", server_default=None)


def downgrade() -> None:
    op.drop_column("sender_profiles", "other_links")
