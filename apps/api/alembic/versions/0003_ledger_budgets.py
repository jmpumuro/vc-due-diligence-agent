"""external operation ledger and budget reservations (Stage 3)

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "external_operations",
        sa.Column("operation_id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("firm_id", sa.String(64), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("activity_type", sa.String(128), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reservation_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("provider_request_id", sa.String(255), nullable=True),
        sa.Column("result_ref", sa.String(512), nullable=True),
        sa.Column("actual_cost", sa.Numeric(12, 6), nullable=True),
        sa.Column("estimated_cost", sa.Numeric(12, 6), nullable=True),
        sa.Column("cost_certainty", sa.String(16), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("possible_duplicate_spend", sa.Boolean(), server_default="false"),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_external_operations_firm", "external_operations", ["firm_id"])
    op.create_table(
        "budget_reservations",
        sa.Column("reservation_id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("operation_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("firm_id", sa.String(64), nullable=False),
        sa.Column("levels_json", postgresql.JSONB(), nullable=False),
        sa.Column("reserved_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("settled_usd", sa.Numeric(12, 6), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("budget_reservations")
    op.drop_index("ix_external_operations_firm", table_name="external_operations")
    op.drop_table("external_operations")
