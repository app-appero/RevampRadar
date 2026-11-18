"""Free-only audit mode (no AI, no PageSpeed).

Revision ID: 0023_audit_free_only
Revises: 0022_activity_outreach
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_audit_free_only"
down_revision: str | None = "0022_activity_outreach"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Gli audit esistenti sono stati eseguiti in modalità completa: default false.
    op.add_column(
        "audits",
        sa.Column("free_only", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("audits", "free_only", server_default=None)


def downgrade() -> None:
    op.drop_column("audits", "free_only")
