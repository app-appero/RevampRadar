"""Proposed contact channel and observed site issue on opportunities.

Revision ID: 0026_opportunity_channel_issue
Revises: 0025_discovery_heartbeat_stats
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_opportunity_channel_issue"
down_revision: str | None = "0025_discovery_heartbeat_stats"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Solo colonne vuote: i tag esistenti (es. canale-ig-proposto) non vengono convertiti.
    op.add_column("opportunities", sa.Column("proposed_channel", sa.String(length=32), nullable=True))
    op.add_column("opportunities", sa.Column("observed_issue", sa.Text(), nullable=True))
    op.create_index("ix_opportunities_proposed_channel", "opportunities", ["proposed_channel"])


def downgrade() -> None:
    op.drop_index("ix_opportunities_proposed_channel", table_name="opportunities")
    op.drop_column("opportunities", "observed_issue")
    op.drop_column("opportunities", "proposed_channel")
