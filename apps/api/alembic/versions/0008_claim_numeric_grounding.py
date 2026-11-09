"""claim numeric grounding fields

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "claims",
        sa.Column("numeric_facts", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.add_column(
        "claims",
        sa.Column(
            "numeric_facts_grounded",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("claims", "numeric_facts_grounded")
    op.drop_column("claims", "numeric_facts")
