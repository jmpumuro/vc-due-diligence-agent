"""claims, contradictions, evidence snapshots/spans, domain progress events

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-08
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("assessments", sa.Column("company_id", postgresql.UUID(as_uuid=False), nullable=True))
    op.create_index("ix_assessments_company_id", "assessments", ["company_id"])

    op.create_table(
        "evidence_snapshots",
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("firm_id", sa.String(64), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_type", sa.String(128), nullable=False),
        sa.Column("normalized_sha256", sa.String(64), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("classification", sa.String(32), nullable=False, server_default="public"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_evidence_snapshots_firm", "evidence_snapshots", ["firm_id"])
    op.create_index("ix_evidence_snapshots_sha", "evidence_snapshots", ["normalized_sha256"])

    op.create_table(
        "evidence_spans",
        sa.Column("span_id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("firm_id", sa.String(64), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_sha256", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_evidence_spans_firm", "evidence_spans", ["firm_id"])
    op.create_index("ix_evidence_spans_snapshot", "evidence_spans", ["snapshot_id"])

    op.create_table(
        "claims",
        sa.Column("claim_id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("firm_id", sa.String(64), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("domain_id", sa.String(64), nullable=False),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("claim_type", sa.String(32), nullable=False, server_default="fact"),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("predicate", sa.Text(), nullable=True),
        sa.Column("object", sa.Text(), nullable=True),
        sa.Column("trust_state", sa.String(32), nullable=False),
        sa.Column("verification_status", sa.String(32), nullable=False, server_default="extracted"),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False, server_default="0.5000"),
        sa.Column("evidence_quality", sa.String(16), nullable=False, server_default="mixed"),
        sa.Column("evidence_span_ids", postgresql.JSONB(), nullable=False),
        sa.Column("snapshot_ids", postgresql.JSONB(), nullable=False),
        sa.Column("supporting_claim_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("contradicting_claim_ids", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("source_urls", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("company_authored", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        # Immutable lineage: statement/spans/snapshots never updated in place after insert.
    )
    op.create_index("ix_claims_firm_assessment", "claims", ["firm_id", "assessment_id"])
    op.create_index("ix_claims_assessment_revision", "claims", ["assessment_id", "revision"])
    op.create_index("ix_claims_domain", "claims", ["domain_id"])
    op.create_index("ix_claims_company", "claims", ["company_id"])

    op.create_table(
        "contradictions",
        sa.Column("contradiction_id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("firm_id", sa.String(64), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("domain_ids", postgresql.JSONB(), nullable=False),
        sa.Column("claim_ids", postgresql.JSONB(), nullable=False),
        sa.Column("contradiction_type", sa.String(32), nullable=False, server_default="other"),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("evidence_for", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("evidence_against", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("resolution", sa.String(32), nullable=False, server_default="open"),
        sa.Column("human_review_state", sa.String(32), nullable=False, server_default="none"),
        sa.Column("trust_impact", sa.String(32), nullable=False, server_default="contested"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_contradictions_firm_assessment", "contradictions", ["firm_id", "assessment_id"]
    )
    op.create_index("ix_contradictions_resolution", "contradictions", ["resolution"])

    op.create_table(
        "contradiction_resolution_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("firm_id", sa.String(64), nullable=False),
        sa.Column("contradiction_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("from_resolution", sa.String(32), nullable=False),
        sa.Column("to_resolution", sa.String(32), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("expected_version", sa.Integer(), nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_contradiction_res_events_c",
        "contradiction_resolution_events",
        ["contradiction_id"],
    )

    op.create_table(
        "domain_progress_events",
        sa.Column("event_id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("firm_id", sa.String(64), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("domain_id", sa.String(64), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_domain_progress_stream",
        "domain_progress_events",
        ["firm_id", "assessment_id", "event_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_domain_progress_stream", table_name="domain_progress_events")
    op.drop_table("domain_progress_events")
    op.drop_index("ix_contradiction_res_events_c", table_name="contradiction_resolution_events")
    op.drop_table("contradiction_resolution_events")
    op.drop_index("ix_contradictions_resolution", table_name="contradictions")
    op.drop_index("ix_contradictions_firm_assessment", table_name="contradictions")
    op.drop_table("contradictions")
    op.drop_index("ix_claims_company", table_name="claims")
    op.drop_index("ix_claims_domain", table_name="claims")
    op.drop_index("ix_claims_assessment_revision", table_name="claims")
    op.drop_index("ix_claims_firm_assessment", table_name="claims")
    op.drop_table("claims")
    op.drop_index("ix_evidence_spans_snapshot", table_name="evidence_spans")
    op.drop_index("ix_evidence_spans_firm", table_name="evidence_spans")
    op.drop_table("evidence_spans")
    op.drop_index("ix_evidence_snapshots_sha", table_name="evidence_snapshots")
    op.drop_index("ix_evidence_snapshots_firm", table_name="evidence_snapshots")
    op.drop_table("evidence_snapshots")
    op.drop_index("ix_assessments_company_id", table_name="assessments")
    op.drop_column("assessments", "company_id")
