"""AI provider credentials editable from Settings.

Revision ID: 0017_ai_credentials
Revises: 0016_email_templates
Create Date: 2026-09-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_ai_credentials"
down_revision: str | None = "0016_email_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_credentials",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False, server_default="claude"),
        sa.Column("anthropic_api_key", sa.Text(), nullable=True),
        sa.Column("openai_api_key", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.alter_column("ai_credentials", "provider", server_default=None)


def downgrade() -> None:
    op.drop_table("ai_credentials")
