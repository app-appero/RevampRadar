"""Discovery: optional filter to drop uncontactable businesses.

Revision ID: 0015_require_contactable
Revises: 0014_growth_scores
Create Date: 2026-09-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_require_contactable"
down_revision: str | None = "0014_growth_scores"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "discovery_runs",
        sa.Column("require_contactable", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("discovery_runs", "require_contactable", server_default=None)


def downgrade() -> None:
    op.drop_column("discovery_runs", "require_contactable")
