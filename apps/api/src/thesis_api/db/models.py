"""Stage-2 persistence — firms, users, sessions, assessments, seed markers."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Firm(Base):
    __tablename__ = "firms"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AppUser(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(255))
    firm_id: Mapped[str] = mapped_column(String(64))
    roles: Mapped[list] = mapped_column(JSONB, default=list)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SessionRow(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), index=True)
    firm_id: Mapped[str] = mapped_column(String(64))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SetupToken(Base):
    __tablename__ = "setup_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SystemFlag(Base):
    __tablename__ = "system_flags"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SeedMarker(Base):
    __tablename__ = "seed_markers"

    name: Mapped[str] = mapped_column(String(128), primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class AssessmentRow(Base):
    __tablename__ = "assessments"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True)
    firm_id: Mapped[str] = mapped_column(String(64), index=True)
    company_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), nullable=True, index=True)
    company_name: Mapped[str] = mapped_column(String(255))
    level: Mapped[int] = mapped_column(default=1)
    state: Mapped[str] = mapped_column(String(64), default="CREATED")
    revision: Mapped[int] = mapped_column(default=1)
    summary_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    workflow_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    review_target_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
