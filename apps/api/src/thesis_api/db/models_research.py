"""Stage 4–5: claims, contradictions, evidence refs, durable domain progress."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from thesis_api.db.models import Base


class EvidenceSnapshotRow(Base):
    __tablename__ = "evidence_snapshots"

    snapshot_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    firm_id: Mapped[str] = mapped_column(String(64), index=True)
    canonical_url: Mapped[str] = mapped_column(Text)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    content_type: Mapped[str] = mapped_column(String(128))
    normalized_sha256: Mapped[str] = mapped_column(String(64), index=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    classification: Mapped[str] = mapped_column(String(32), default="public")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvidenceSpanRow(Base):
    __tablename__ = "evidence_spans"

    span_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    firm_id: Mapped[str] = mapped_column(String(64), index=True)
    snapshot_id: Mapped[str] = mapped_column(UUID(as_uuid=False), index=True)
    start_offset: Mapped[int] = mapped_column(Integer)
    end_offset: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    text_sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ClaimRow(Base):
    __tablename__ = "claims"

    claim_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    firm_id: Mapped[str] = mapped_column(String(64), index=True)
    assessment_id: Mapped[str] = mapped_column(UUID(as_uuid=False), index=True)
    company_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True, index=True)
    revision: Mapped[int] = mapped_column(Integer)
    domain_id: Mapped[str] = mapped_column(String(64), index=True)
    statement: Mapped[str] = mapped_column(Text)
    claim_type: Mapped[str] = mapped_column(String(32), default="fact")
    subject: Mapped[str] = mapped_column(Text)
    predicate: Mapped[str | None] = mapped_column(Text, nullable=True)
    object: Mapped[str | None] = mapped_column(Text, nullable=True)
    trust_state: Mapped[str] = mapped_column(String(32))
    verification_status: Mapped[str] = mapped_column(String(32), default="extracted")
    confidence: Mapped[Decimal] = mapped_column(Numeric(5, 4), default=Decimal("0.5000"))
    evidence_quality: Mapped[str] = mapped_column(String(16), default="mixed")
    # Immutable lineage after insert — repositories refuse in-place mutation.
    evidence_span_ids: Mapped[list] = mapped_column(JSONB)
    snapshot_ids: Mapped[list] = mapped_column(JSONB)
    supporting_claim_ids: Mapped[list] = mapped_column(JSONB, default=list)
    contradicting_claim_ids: Mapped[list] = mapped_column(JSONB, default=list)
    source_urls: Mapped[list] = mapped_column(JSONB, default=list)
    numeric_facts: Mapped[list] = mapped_column(JSONB, default=list)
    numeric_facts_grounded: Mapped[list] = mapped_column(JSONB, default=list)
    company_authored: Mapped[bool] = mapped_column(Boolean, default=False)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContradictionRow(Base):
    __tablename__ = "contradictions"

    contradiction_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    firm_id: Mapped[str] = mapped_column(String(64), index=True)
    assessment_id: Mapped[str] = mapped_column(UUID(as_uuid=False), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    domain_ids: Mapped[list] = mapped_column(JSONB)
    claim_ids: Mapped[list] = mapped_column(JSONB)
    contradiction_type: Mapped[str] = mapped_column(String(32), default="other")
    severity: Mapped[str] = mapped_column(String(16))
    explanation: Mapped[str] = mapped_column(Text)
    evidence_for: Mapped[list] = mapped_column(JSONB, default=list)
    evidence_against: Mapped[list] = mapped_column(JSONB, default=list)
    resolution: Mapped[str] = mapped_column(String(32), default="open")
    human_review_state: Mapped[str] = mapped_column(String(32), default="none")
    trust_impact: Mapped[str] = mapped_column(String(32), default="contested")
    version: Mapped[int] = mapped_column(Integer, default=1)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContradictionResolutionEventRow(Base):
    __tablename__ = "contradiction_resolution_events"

    event_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    firm_id: Mapped[str] = mapped_column(String(64))
    contradiction_id: Mapped[str] = mapped_column(UUID(as_uuid=False), index=True)
    from_resolution: Mapped[str] = mapped_column(String(32))
    to_resolution: Mapped[str] = mapped_column(String(32))
    actor_user_id: Mapped[str] = mapped_column(UUID(as_uuid=False))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_version: Mapped[int] = mapped_column(Integer)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DomainProgressEventRow(Base):
    __tablename__ = "domain_progress_events"

    event_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    firm_id: Mapped[str] = mapped_column(String(64))
    assessment_id: Mapped[str] = mapped_column(UUID(as_uuid=False))
    revision: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(64))
    domain_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
