"""Localita' di riferimento e soglia di priorita' locale sul profilo mittente.

Revision ID: 0021_local_priority
Revises: 0020_design_briefs_concepts
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_local_priority"
down_revision: str | None = "0020_design_briefs_concepts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("sender_profiles", sa.Column("reference_location", sa.String(length=255), nullable=True))
    op.add_column("sender_profiles", sa.Column("reference_latitude", sa.Float(), nullable=True))
    op.add_column("sender_profiles", sa.Column("reference_longitude", sa.Float(), nullable=True))
    op.add_column("sender_profiles", sa.Column("local_radius_km", sa.Float(), nullable=True))
    op.add_column(
        "sender_profiles",
        sa.Column("local_mention_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("sender_profiles", "local_mention_enabled", server_default=None)
    op.add_column("sender_profiles", sa.Column("local_mention_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("sender_profiles", "local_mention_text")
    op.drop_column("sender_profiles", "local_mention_enabled")
    op.drop_column("sender_profiles", "local_radius_km")
    op.drop_column("sender_profiles", "reference_longitude")
    op.drop_column("sender_profiles", "reference_latitude")
    op.drop_column("sender_profiles", "reference_location")
