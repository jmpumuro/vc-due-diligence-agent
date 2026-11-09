"""reviews, deal teams, outbox, watchlists, retention scaffolding

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "deal_team_members",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("firm_id", sa.String(64), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="member"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("assessment_id", "user_id", name="uq_deal_team_member"),
    )
    op.create_index("ix_deal_team_firm_assessment", "deal_team_members", ["firm_id", "assessment_id"])

    op.create_table(
        "review_targets",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("firm_id", sa.String(64), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("assessment_revision", sa.Integer(), nullable=False),
        sa.Column("evidence_snapshot_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("evaluation_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("memo_version_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("review_policy_version", sa.String(64), nullable=False),
        sa.Column("target_digest", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_review_targets_assessment", "review_targets", ["firm_id", "assessment_id"])

    op.create_table(
        "review_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("firm_id", sa.String(64), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("target_digest", sa.String(64), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("requested_items", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("firm_id", "idempotency_key", name="uq_review_idempotency"),
    )

    op.create_table(
        "outbox_events",
        sa.Column("outbox_id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("firm_id", sa.String(64), nullable=False),
        sa.Column("subject_type", sa.String(64), nullable=False),
        sa.Column("subject_id", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("firm_id", "idempotency_key", name="uq_outbox_idempotency"),
    )
    op.create_index(
        "ix_outbox_pending",
        "outbox_events",
        ["firm_id", "status", "created_at"],
    )

    op.create_table(
        "watchlist_entries",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("firm_id", sa.String(64), nullable=False),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("primary_domain", sa.String(255), nullable=True),
        sa.Column("rules", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("cadence", sa.String(32), nullable=False, server_default="weekly"),
        sa.Column("paused", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_by", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_watchlist_firm", "watchlist_entries", ["firm_id"])

    op.create_table(
        "data_rooms",
        sa.Column("data_room_id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("firm_id", sa.String(64), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("object_prefix", sa.Text(), nullable=False),
        sa.Column("delete_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("assessment_id", name="uq_data_room_assessment"),
    )

    op.create_table(
        "retention_records",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("firm_id", sa.String(64), nullable=False),
        sa.Column("data_room_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delete_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retention_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.add_column(
        "assessments",
        sa.Column("workflow_id", sa.String(255), nullable=True),
    )
    op.add_column(
        "assessments",
        sa.Column("review_target_digest", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("assessments", "review_target_digest")
    op.drop_column("assessments", "workflow_id")
    op.drop_table("retention_records")
    op.drop_table("data_rooms")
    op.drop_index("ix_watchlist_firm", table_name="watchlist_entries")
    op.drop_table("watchlist_entries")
    op.drop_index("ix_outbox_pending", table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_table("review_decisions")
    op.drop_index("ix_review_targets_assessment", table_name="review_targets")
    op.drop_table("review_targets")
    op.drop_index("ix_deal_team_firm_assessment", table_name="deal_team_members")
    op.drop_table("deal_team_members")
