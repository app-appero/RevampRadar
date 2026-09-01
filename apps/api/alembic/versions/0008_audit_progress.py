"""Audit scan progress percent and label.

Revision ID: 0008_audit_progress
Revises: 0007_proposals
Create Date: 2026-08-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_audit_progress"
down_revision: str | None = "0007_proposals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "audits",
        sa.Column("progress_percent", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("audits", sa.Column("progress_label", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("audits", "progress_label")
    op.drop_column("audits", "progress_percent")
