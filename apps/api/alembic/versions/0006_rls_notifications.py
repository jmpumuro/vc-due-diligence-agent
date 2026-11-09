"""RLS policies + in-app notifications (Stages 7–8 / REM-P0-02)

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tenant-scoped tables. Auth tables (users/sessions/firms/…) stay unrestricted so
# login can resolve the session before SET LOCAL app.firm_id.
FIRM_TABLES = (
    "assessments",
    "external_operations",
    "budget_reservations",
    "evidence_snapshots",
    "evidence_spans",
    "claims",
    "contradictions",
    "contradiction_resolution_events",
    "domain_progress_events",
    "deal_team_members",
    "review_targets",
    "review_decisions",
    "outbox_events",
    "watchlist_entries",
    "data_rooms",
    "retention_records",
    "notifications",
)


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("firm_id", sa.String(64), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("outbox_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("subject_type", sa.String(64), nullable=False),
        sa.Column("subject_id", sa.String(128), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("firm_id", "outbox_id", name="uq_notification_outbox"),
    )
    op.create_index(
        "ix_notifications_firm_created",
        "notifications",
        ["firm_id", "created_at"],
    )

    # App role for non-owner access (table owner still bypasses RLS unless FORCE).
    op.execute(
        """
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'thesis_app') THEN
            CREATE ROLE thesis_app NOLOGIN;
          END IF;
        END
        $$;
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO thesis_app")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO thesis_app"
    )
    op.execute(
        "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO thesis_app"
    )
    op.execute(
        """
        ALTER DEFAULT PRIVILEGES IN SCHEMA public
        GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO thesis_app
        """
    )

    for table in FIRM_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        # Drop if re-run / partial apply
        op.execute(f"DROP POLICY IF EXISTS firm_isolation ON {table}")
        op.execute(
            f"""
            CREATE POLICY firm_isolation ON {table}
              AS PERMISSIVE
              FOR ALL
              TO thesis_app
              USING (firm_id = NULLIF(current_setting('app.firm_id', true), ''))
              WITH CHECK (firm_id = NULLIF(current_setting('app.firm_id', true), ''))
            """
        )


def downgrade() -> None:
    for table in FIRM_TABLES:
        op.execute(f"DROP POLICY IF EXISTS firm_isolation ON {table}")
        # notifications dropped below; skip RLS disable if table gone
        if table == "notifications":
            continue
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.drop_index("ix_notifications_firm_created", table_name="notifications")
    op.drop_table("notifications")
