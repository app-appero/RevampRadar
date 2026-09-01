"""Discovery extended flag (include businesses without a website).

Revision ID: 0012_discovery_extended
Revises: 0011_company_coords
Create Date: 2026-08-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_discovery_extended"
down_revision: str | None = "0011_company_coords"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "discovery_runs",
        sa.Column("extended", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("discovery_runs", "extended")
