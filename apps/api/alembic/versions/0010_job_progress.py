"""Discovery and bulk scan progress percent.

Revision ID: 0010_job_progress
Revises: 0009_sender_profile
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_job_progress"
down_revision: str | None = "0009_sender_profile"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "discovery_runs",
        sa.Column("progress_percent", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("discovery_runs", sa.Column("progress_label", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("discovery_runs", "progress_label")
    op.drop_column("discovery_runs", "progress_percent")
