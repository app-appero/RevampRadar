"""Google Places API key editable from Settings.

Revision ID: 0019_google_places_key
Revises: 0018_sender_other_links
Create Date: 2026-09-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019_google_places_key"
down_revision: str | None = "0018_sender_other_links"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ai_credentials", sa.Column("google_places_api_key", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_credentials", "google_places_api_key")
