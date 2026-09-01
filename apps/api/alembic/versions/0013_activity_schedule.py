"""Scheduled activities (due_at) for agenda.

Revision ID: 0013_activity_schedule
Revises: 0012_discovery_extended
Create Date: 2026-09-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_activity_schedule"
down_revision: str | None = "0012_discovery_extended"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("activities", sa.Column("due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("activities", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.alter_column("activities", "occurred_at", existing_type=sa.DateTime(timezone=True), nullable=True)
    op.create_index("ix_activities_due_at", "activities", ["due_at"])


def downgrade() -> None:
    op.drop_index("ix_activities_due_at", table_name="activities")
    op.alter_column("activities", "occurred_at", existing_type=sa.DateTime(timezone=True), nullable=False)
    op.drop_column("activities", "completed_at")
    op.drop_column("activities", "due_at")
