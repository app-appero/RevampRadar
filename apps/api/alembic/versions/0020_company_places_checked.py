"""Track completed Google Places contact checks.

Revision ID: 0020_company_places_checked
Revises: 0019_google_places_key
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020_company_places_checked"
down_revision: str | None = "0019_google_places_key"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("places_checked_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("companies", "places_checked_at")
