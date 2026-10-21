"""Control sender website visibility in generated email signatures.

Revision ID: 0021_sender_signature_visibility
Revises: 0020_company_places_checked
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_sender_signature_visibility"
down_revision: str | None = "0020_company_places_checked"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sender_profiles",
        sa.Column("website_in_signature", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.alter_column("sender_profiles", "website_in_signature", server_default=None)


def downgrade() -> None:
    op.drop_column("sender_profiles", "website_in_signature")
