"""Design Brief e Concept Homepage HTML (versionati) per prospect approfonditi.

Revision ID: 0020_design_briefs_concepts
Revises: 0019_company_research
Create Date: 2026-09-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_design_briefs_concepts"
down_revision: str | None = "0019_company_research"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "design_briefs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("style", sa.String(length=64), nullable=True),
        sa.Column("palette", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("typography", sa.String(length=255), nullable=True),
        sa.Column("tone_of_voice", sa.String(length=255), nullable=True),
        sa.Column("spacing", sa.String(length=32), nullable=True),
        sa.Column("border_radius", sa.String(length=32), nullable=True),
        sa.Column("image_treatment", sa.String(length=255), nullable=True),
        sa.Column("primary_cta", sa.String(length=128), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="auto"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id"),
    )
    op.create_index("ix_design_briefs_company_id", "design_briefs", ["company_id"])
    op.alter_column("design_briefs", "source", server_default=None)

    op.create_table(
        "concepts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="generating"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("html_path", sa.String(length=1024), nullable=False),
        sa.Column("css_path", sa.String(length=1024), nullable=False),
        sa.Column("assets_dir", sa.String(length=1024), nullable=True),
        sa.Column("sections", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("design_brief_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("company_brief_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("generator_version", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False, server_default="deterministic"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_concepts_company_id", "concepts", ["company_id"])
    op.create_index("ix_concepts_status", "concepts", ["status"])
    op.create_index("ix_concepts_is_current", "concepts", ["is_current"])
    op.alter_column("concepts", "status", server_default=None)
    op.alter_column("concepts", "is_current", server_default=None)
    op.alter_column("concepts", "source", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_concepts_is_current", table_name="concepts")
    op.drop_index("ix_concepts_status", table_name="concepts")
    op.drop_index("ix_concepts_company_id", table_name="concepts")
    op.drop_table("concepts")
    op.drop_index("ix_design_briefs_company_id", table_name="design_briefs")
    op.drop_table("design_briefs")
