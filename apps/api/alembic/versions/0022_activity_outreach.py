"""Historical outreach fields on activities.

Revision ID: 0022_activity_outreach
Revises: 0021_sender_signature_visibility
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_activity_outreach"
down_revision: str | None = "0021_sender_signature_visibility"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("activities", sa.Column("occurred_on", sa.Date(), nullable=True))
    op.add_column("activities", sa.Column("channel", sa.String(length=32), nullable=True))
    op.add_column("activities", sa.Column("sender", sa.String(length=255), nullable=True))
    op.add_column("activities", sa.Column("recipient", sa.String(length=255), nullable=True))
    op.add_column("activities", sa.Column("batch_id", sa.String(length=128), nullable=True))
    op.add_column("activities", sa.Column("external_ref", sa.String(length=255), nullable=True))
    op.create_index("ix_activities_batch_id", "activities", ["batch_id"])
    op.create_index("uq_activities_external_ref", "activities", ["external_ref"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_activities_external_ref", table_name="activities")
    op.drop_index("ix_activities_batch_id", table_name="activities")
    op.drop_column("activities", "external_ref")
    op.drop_column("activities", "batch_id")
    op.drop_column("activities", "recipient")
    op.drop_column("activities", "sender")
    op.drop_column("activities", "channel")
    op.drop_column("activities", "occurred_on")
