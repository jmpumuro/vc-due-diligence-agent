"""Persistent contradictions with version-checked human resolution."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from thesis_api.db.models_research import ContradictionResolutionEventRow, ContradictionRow
from thesis_api.tenant import TenantContext, TenantIsolationError
from thesis_contracts.research import ContradictionRecord, ContradictionResolutionEvent


class VersionConflictError(ValueError):
    """Optimistic concurrency failure on contradiction resolution."""


def _uuids_to_str(ids: list[UUID]) -> list[str]:
    return [str(i) for i in ids]


def _str_to_uuids(ids: list) -> list[UUID]:
    return [UUID(str(i)) for i in ids]


def contradiction_from_row(row: ContradictionRow) -> ContradictionRecord:
    return ContradictionRecord(
        contradiction_id=UUID(row.contradiction_id),
        firm_id=row.firm_id,
        assessment_id=UUID(row.assessment_id),
        revision=row.revision,
        domain_ids=list(row.domain_ids or []),  # type: ignore[arg-type]
        claim_ids=_str_to_uuids(row.claim_ids or []),
        contradiction_type=row.contradiction_type,  # type: ignore[arg-type]
        severity=row.severity,  # type: ignore[arg-type]
        explanation=row.explanation,
        evidence_for=_str_to_uuids(row.evidence_for or []),
        evidence_against=_str_to_uuids(row.evidence_against or []),
        resolution=row.resolution,  # type: ignore[arg-type]
        human_review_state=row.human_review_state,  # type: ignore[arg-type]
        trust_impact=row.trust_impact,  # type: ignore[arg-type]
        version=row.version,
        schema_version=row.schema_version,
    )


async def insert_contradiction(
    session: AsyncSession,
    tenant: TenantContext,
    record: ContradictionRecord,
) -> ContradictionRecord:
    if record.firm_id and record.firm_id != tenant.firm_id:
        raise TenantIsolationError("contradiction firm mismatch")
    existing = await session.get(ContradictionRow, str(record.contradiction_id))
    if existing is not None:
        tenant.assert_firm(existing.firm_id)
        return contradiction_from_row(existing)

    row = ContradictionRow(
        contradiction_id=str(record.contradiction_id),
        firm_id=tenant.firm_id,
        assessment_id=str(record.assessment_id),
        revision=record.revision,
        domain_ids=list(record.domain_ids),
        claim_ids=_uuids_to_str(record.claim_ids),
        contradiction_type=record.contradiction_type,
        severity=record.severity,
        explanation=record.explanation,
        evidence_for=_uuids_to_str(record.evidence_for),
        evidence_against=_uuids_to_str(record.evidence_against),
        resolution=record.resolution,
        human_review_state=record.human_review_state,
        trust_impact=record.trust_impact,
        version=record.version,
        schema_version=record.schema_version,
    )
    session.add(row)
    await session.flush()
    return contradiction_from_row(row)


async def get_contradiction(
    session: AsyncSession,
    tenant: TenantContext,
    contradiction_id: str,
) -> ContradictionRecord | None:
    row = await session.get(ContradictionRow, contradiction_id)
    if row is None:
        return None
    tenant.assert_firm(row.firm_id)
    return contradiction_from_row(row)


async def list_contradictions(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    assessment_id: str,
    resolution: str | None = None,
    revision: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[ContradictionRecord], int]:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    filters = [
        ContradictionRow.firm_id == tenant.firm_id,
        ContradictionRow.assessment_id == assessment_id,
    ]
    if resolution:
        filters.append(ContradictionRow.resolution == resolution)
    if revision is not None:
        filters.append(ContradictionRow.revision == revision)

    total = (
        await session.execute(
            select(func.count()).select_from(ContradictionRow).where(and_(*filters))
        )
    ).scalar_one()
    rows = (
        await session.execute(
            select(ContradictionRow)
            .where(and_(*filters))
            .order_by(ContradictionRow.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return [contradiction_from_row(r) for r in rows], int(total)


async def resolve_contradiction(
    session: AsyncSession,
    tenant: TenantContext,
    contradiction_id: str,
    *,
    expected_version: int,
    new_resolution: str,
    comment: str | None = None,
    human_review_state: str = "decided",
) -> ContradictionRecord:
    row = await session.get(ContradictionRow, contradiction_id)
    if row is None:
        raise KeyError(contradiction_id)
    tenant.assert_firm(row.firm_id)
    if row.version != expected_version:
        raise VersionConflictError(
            f"version mismatch: expected={expected_version} actual={row.version}"
        )
    from_res = row.resolution
    row.resolution = new_resolution
    row.human_review_state = human_review_state
    row.version = row.version + 1
    row.updated_at = datetime.now(timezone.utc)

    event = ContradictionResolutionEventRow(
        event_id=str(uuid4()),
        firm_id=tenant.firm_id,
        contradiction_id=contradiction_id,
        from_resolution=from_res,
        to_resolution=new_resolution,
        actor_user_id=tenant.user_id,
        comment=comment,
        expected_version=expected_version,
    )
    session.add(event)
    await session.flush()
    return contradiction_from_row(row)


async def list_resolution_history(
    session: AsyncSession,
    tenant: TenantContext,
    contradiction_id: str,
) -> list[ContradictionResolutionEvent]:
    row = await session.get(ContradictionRow, contradiction_id)
    if row is None:
        raise KeyError(contradiction_id)
    tenant.assert_firm(row.firm_id)
    events = (
        await session.execute(
            select(ContradictionResolutionEventRow)
            .where(
                ContradictionResolutionEventRow.contradiction_id == contradiction_id,
                ContradictionResolutionEventRow.firm_id == tenant.firm_id,
            )
            .order_by(ContradictionResolutionEventRow.at.asc())
        )
    ).scalars().all()
    return [
        ContradictionResolutionEvent(
            event_id=UUID(e.event_id),
            contradiction_id=UUID(e.contradiction_id),
            from_resolution=e.from_resolution,
            to_resolution=e.to_resolution,
            actor_user_id=UUID(e.actor_user_id),
            comment=e.comment,
            expected_version=e.expected_version,
            at=e.at,
        )
        for e in events
    ]
