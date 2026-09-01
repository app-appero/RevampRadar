"""Company latitude and longitude from OSM.

Revision ID: 0011_company_coords
Revises: 0010_job_progress
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_company_coords"
down_revision: str | None = "0010_job_progress"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("latitude", sa.Float(), nullable=True))
    op.add_column("companies", sa.Column("longitude", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("companies", "longitude")
    op.drop_column("companies", "latitude")
