"""Document versions for data-room uploads (ClamAV / worker-docs path).

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("document_id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("firm_id", sa.String(64), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("data_room_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("filename", sa.String(512), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=True),
        sa.Column("byte_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="uploaded"),
        sa.Column("object_bucket", sa.String(64), nullable=False),
        sa.Column("object_key", sa.String(1024), nullable=False),
        sa.Column("scan_detail", sa.Text(), nullable=True),
        sa.Column("ocr_pages", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_documents_firm_assessment", "documents", ["firm_id", "assessment_id"])
    op.execute("ALTER TABLE documents ENABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS firm_isolation ON documents")
    op.execute(
        """
        CREATE POLICY firm_isolation ON documents
          AS PERMISSIVE
          FOR ALL
          TO thesis_app
          USING (firm_id = NULLIF(current_setting('app.firm_id', true), ''))
          WITH CHECK (firm_id = NULLIF(current_setting('app.firm_id', true), ''))
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS firm_isolation ON documents")
    op.drop_index("ix_documents_firm_assessment", table_name="documents")
    op.drop_table("documents")
