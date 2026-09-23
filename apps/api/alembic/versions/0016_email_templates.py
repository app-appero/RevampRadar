"""Editable proposal email templates.

Revision ID: 0016_email_templates
Revises: 0015_require_contactable
Create Date: 2026-09-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_email_templates"
down_revision: str | None = "0015_require_contactable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("refactor_body", sa.Text(), nullable=True),
        sa.Column("greenfield_body", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("email_templates")
