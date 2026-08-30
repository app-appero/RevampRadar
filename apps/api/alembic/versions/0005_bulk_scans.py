"""Bulk scan jobs.

Revision ID: 0005_bulk_scans
Revises: 0004_discovery
Create Date: 2026-08-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_bulk_scans"
down_revision: str | None = "0004_discovery"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_opportunity_scores_company_id",
        "opportunity_scores",
        "companies",
        ["company_id"],
        ["id"],
    )
    op.create_index("ix_opportunity_scores_company_id", "opportunity_scores", ["company_id"])

    op.create_table(
        "bulk_scans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("discovery_run_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("concurrency", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["discovery_run_id"], ["discovery_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bulk_scans_discovery_run_id", "bulk_scans", ["discovery_run_id"])
    op.create_index("ix_bulk_scans_status", "bulk_scans", ["status"])

    op.create_table(
        "bulk_scan_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("bulk_scan_id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("audit_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["audit_id"], ["audits.id"]),
        sa.ForeignKeyConstraint(["bulk_scan_id"], ["bulk_scans.id"]),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bulk_scan_items_bulk_scan_id", "bulk_scan_items", ["bulk_scan_id"])
    op.create_index("ix_bulk_scan_items_company_id", "bulk_scan_items", ["company_id"])
    op.create_index("ix_bulk_scan_items_status", "bulk_scan_items", ["status"])


def downgrade() -> None:
    op.drop_table("bulk_scan_items")
    op.drop_table("bulk_scans")
    op.drop_index("ix_opportunity_scores_company_id", table_name="opportunity_scores")
    op.drop_constraint("fk_opportunity_scores_company_id", "opportunity_scores", type_="foreignkey")
