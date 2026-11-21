"""Discovery heartbeat (stale run detection) and yield stats.

Revision ID: 0025_discovery_heartbeat_stats
Revises: 0024_company_instagram
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025_discovery_heartbeat_stats"
down_revision: str | None = "0024_company_instagram"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("discovery_runs", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "discovery_runs",
        sa.Column("stats", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("discovery_runs", "stats")
    op.drop_column("discovery_runs", "heartbeat_at")
