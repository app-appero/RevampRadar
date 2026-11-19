"""Instagram handle and last post date on companies.

Revision ID: 0024_company_instagram
Revises: 0023_audit_free_only
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024_company_instagram"
down_revision: str | None = "0023_audit_free_only"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("instagram_handle", sa.String(length=64), nullable=True))
    op.add_column("companies", sa.Column("instagram_last_post_at", sa.Date(), nullable=True))
    op.create_index("ix_companies_instagram_handle", "companies", ["instagram_handle"])
    op.create_index("ix_companies_instagram_last_post_at", "companies", ["instagram_last_post_at"])


def downgrade() -> None:
    op.drop_index("ix_companies_instagram_last_post_at", table_name="companies")
    op.drop_index("ix_companies_instagram_handle", table_name="companies")
    op.drop_column("companies", "instagram_last_post_at")
    op.drop_column("companies", "instagram_handle")
