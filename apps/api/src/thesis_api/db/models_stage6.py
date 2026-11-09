"""Stage 6–8 persistence: reviews, outbox, watchlists, data rooms, retention."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from thesis_api.db.models import Base


class DealTeamMemberRow(Base):
    __tablename__ = "deal_team_members"
    __table_args__ = (UniqueConstraint("assessment_id", "user_id", name="uq_deal_team_member"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    firm_id: Mapped[str] = mapped_column(String(64), index=True)
    assessment_id: Mapped[str] = mapped_column(UUID(as_uuid=False), index=True)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False))
    role: Mapped[str] = mapped_column(String(32), default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewTargetRow(Base):
    __tablename__ = "review_targets"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    firm_id: Mapped[str] = mapped_column(String(64))
    assessment_id: Mapped[str] = mapped_column(UUID(as_uuid=False), index=True)
    assessment_revision: Mapped[int] = mapped_column(Integer)
    evidence_snapshot_id: Mapped[str] = mapped_column(UUID(as_uuid=False))
    evaluation_id: Mapped[str] = mapped_column(UUID(as_uuid=False))
    memo_version_id: Mapped[str] = mapped_column(UUID(as_uuid=False))
    review_policy_version: Mapped[str] = mapped_column(String(64))
    target_digest: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewDecisionRow(Base):
    __tablename__ = "review_decisions"
    __table_args__ = (UniqueConstraint("firm_id", "idempotency_key", name="uq_review_idempotency"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    firm_id: Mapped[str] = mapped_column(String(64))
    assessment_id: Mapped[str] = mapped_column(UUID(as_uuid=False))
    target_digest: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(32))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    requested_items: Mapped[list] = mapped_column(JSONB, default=list)
    actor_user_id: Mapped[str] = mapped_column(UUID(as_uuid=False))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OutboxEventRow(Base):
    __tablename__ = "outbox_events"
    __table_args__ = (UniqueConstraint("firm_id", "idempotency_key", name="uq_outbox_idempotency"),)

    outbox_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    firm_id: Mapped[str] = mapped_column(String(64), index=True)
    subject_type: Mapped[str] = mapped_column(String(64))
    subject_id: Mapped[str] = mapped_column(String(128))
    event_type: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    sequence: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WatchlistEntryRow(Base):
    __tablename__ = "watchlist_entries"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    firm_id: Mapped[str] = mapped_column(String(64), index=True)
    company_name: Mapped[str] = mapped_column(String(255))
    primary_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rules: Mapped[dict] = mapped_column(JSONB, default=dict)
    cadence: Mapped[str] = mapped_column(String(32), default="weekly")
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str] = mapped_column(UUID(as_uuid=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DataRoomRow(Base):
    __tablename__ = "data_rooms"
    __table_args__ = (UniqueConstraint("assessment_id", name="uq_data_room_assessment"),)

    data_room_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    firm_id: Mapped[str] = mapped_column(String(64))
    assessment_id: Mapped[str] = mapped_column(UUID(as_uuid=False))
    status: Mapped[str] = mapped_column(String(32), default="open")
    object_prefix: Mapped[str] = mapped_column(Text)
    delete_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    legal_hold: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentRow(Base):
    __tablename__ = "documents"

    document_id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    firm_id: Mapped[str] = mapped_column(String(64), index=True)
    assessment_id: Mapped[str] = mapped_column(UUID(as_uuid=False), index=True)
    data_room_id: Mapped[str] = mapped_column(UUID(as_uuid=False))
    filename: Mapped[str] = mapped_column(String(512))
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    byte_size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="uploaded")
    object_bucket: Mapped[str] = mapped_column(String(64))
    object_key: Mapped[str] = mapped_column(String(1024))
    scan_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_pages: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RetentionRecordRow(Base):
    __tablename__ = "retention_records"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    firm_id: Mapped[str] = mapped_column(String(64))
    data_room_id: Mapped[str] = mapped_column(UUID(as_uuid=False))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delete_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retention_days: Mapped[int] = mapped_column(Integer, default=90)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NotificationRow(Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("firm_id", "outbox_id", name="uq_notification_outbox"),)

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    firm_id: Mapped[str] = mapped_column(String(64), index=True)
    user_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    outbox_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64))
    subject_type: Mapped[str] = mapped_column(String(64))
    subject_id: Mapped[str] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
