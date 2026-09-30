"""Token OpenAPI.com Company modificabile da Impostazioni.

Revision ID: 0022_openapi_company_token
Revises: 0021_local_priority
Create Date: 2026-09-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_openapi_company_token"
down_revision: str | None = "0021_local_priority"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ai_credentials", sa.Column("openapi_company_token", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_credentials", "openapi_company_token")
