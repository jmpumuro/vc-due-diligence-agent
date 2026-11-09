"""stage2 shell tables + pgvector

Revision ID: 0001
Revises:
Create Date: 2026-11-07
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "firms",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("firm_id", sa.String(64), nullable=False),
        sa.Column("roles", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "seed_markers",
        sa.Column("name", sa.String(128), primary_key=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("detail", sa.Text(), nullable=True),
    )
    op.create_table(
        "assessments",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("firm_id", sa.String(64), nullable=False),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("state", sa.String(64), nullable=False, server_default="CREATED"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("summary_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_assessments_firm_id", "assessments", ["firm_id"])


def downgrade() -> None:
    op.drop_index("ix_assessments_firm_id", table_name="assessments")
    op.drop_table("assessments")
    op.drop_table("seed_markers")
    op.drop_table("users")
    op.drop_table("firms")
