"""Persistent claims — immutable evidence lineage; tenant-scoped."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from thesis_api.db.models_research import ClaimRow
from thesis_api.tenant import TenantContext, TenantIsolationError
from thesis_contracts.research import Claim


class ClaimLineageImmutableError(ValueError):
    """Raised when an attempt would overwrite historical evidence refs."""


def _uuids_to_str(ids: list[UUID]) -> list[str]:
    return [str(i) for i in ids]


def _str_to_uuids(ids: list) -> list[UUID]:
    return [UUID(str(i)) for i in ids]


def claim_from_row(row: ClaimRow) -> Claim:
    return Claim(
        claim_id=UUID(row.claim_id),
        firm_id=row.firm_id,
        assessment_id=UUID(row.assessment_id),
        company_id=UUID(row.company_id) if row.company_id else None,
        revision=row.revision,
        domain_id=row.domain_id,  # type: ignore[arg-type]
        statement=row.statement,
        claim_type=row.claim_type,  # type: ignore[arg-type]
        subject=row.subject,
        predicate=row.predicate,
        object=row.object,
        trust_state=row.trust_state,  # type: ignore[arg-type]
        verification_status=row.verification_status,  # type: ignore[arg-type]
        confidence=Decimal(str(row.confidence)),
        evidence_quality=row.evidence_quality,  # type: ignore[arg-type]
        evidence_span_ids=_str_to_uuids(row.evidence_span_ids or []),
        snapshot_ids=_str_to_uuids(row.snapshot_ids or []),
        supporting_claim_ids=_str_to_uuids(row.supporting_claim_ids or []),
        contradicting_claim_ids=_str_to_uuids(row.contradicting_claim_ids or []),
        source_urls=list(row.source_urls or []),
        numeric_facts=list(getattr(row, "numeric_facts", None) or []),
        numeric_facts_grounded=list(getattr(row, "numeric_facts_grounded", None) or []),
        company_authored=row.company_authored,
        schema_version=row.schema_version,
        extracted_at=row.extracted_at,
    )


async def insert_claim(
    session: AsyncSession,
    tenant: TenantContext,
    claim: Claim,
) -> Claim:
    if claim.firm_id and claim.firm_id != tenant.firm_id:
        raise TenantIsolationError("claim firm mismatch")
    existing = await session.get(ClaimRow, str(claim.claim_id))
    if existing is not None:
        tenant.assert_firm(existing.firm_id)
        # Idempotent insert: same lineage OK; divergent lineage is a hard error.
        if (
            existing.evidence_span_ids != _uuids_to_str(claim.evidence_span_ids)
            or existing.snapshot_ids != _uuids_to_str(claim.snapshot_ids)
            or existing.statement != claim.statement
        ):
            raise ClaimLineageImmutableError(
                "cannot overwrite claim lineage; insert a new claim_id instead"
            )
        return claim_from_row(existing)

    row = ClaimRow(
        claim_id=str(claim.claim_id),
        firm_id=tenant.firm_id,
        assessment_id=str(claim.assessment_id),
        company_id=str(claim.company_id) if claim.company_id else None,
        revision=claim.revision,
        domain_id=claim.domain_id,
        statement=claim.statement,
        claim_type=claim.claim_type,
        subject=claim.subject,
        predicate=claim.predicate,
        object=claim.object,
        trust_state=claim.trust_state,
        verification_status=claim.verification_status,
        confidence=claim.confidence,
        evidence_quality=claim.evidence_quality,
        evidence_span_ids=_uuids_to_str(claim.evidence_span_ids),
        snapshot_ids=_uuids_to_str(claim.snapshot_ids),
        supporting_claim_ids=_uuids_to_str(claim.supporting_claim_ids),
        contradicting_claim_ids=_uuids_to_str(claim.contradicting_claim_ids),
        source_urls=list(claim.source_urls),
        numeric_facts=list(claim.numeric_facts or []),
        numeric_facts_grounded=list(claim.numeric_facts_grounded or []),
        company_authored=claim.company_authored,
        schema_version=claim.schema_version,
        extracted_at=claim.extracted_at or datetime.now(timezone.utc),
    )
    session.add(row)
    await session.flush()
    return claim_from_row(row)


async def get_claim(
    session: AsyncSession,
    tenant: TenantContext,
    claim_id: str,
) -> Claim | None:
    row = await session.get(ClaimRow, claim_id)
    if row is None:
        return None
    tenant.assert_firm(row.firm_id)
    return claim_from_row(row)


async def list_claims(
    session: AsyncSession,
    tenant: TenantContext,
    *,
    assessment_id: str,
    domain_id: str | None = None,
    verification_status: str | None = None,
    revision: int | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Claim], int]:
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    filters = [
        ClaimRow.firm_id == tenant.firm_id,
        ClaimRow.assessment_id == assessment_id,
    ]
    if domain_id:
        filters.append(ClaimRow.domain_id == domain_id)
    if verification_status:
        filters.append(ClaimRow.verification_status == verification_status)
    if revision is not None:
        filters.append(ClaimRow.revision == revision)

    total = (
        await session.execute(select(func.count()).select_from(ClaimRow).where(and_(*filters)))
    ).scalar_one()
    rows = (
        await session.execute(
            select(ClaimRow)
            .where(and_(*filters))
            .order_by(ClaimRow.created_at.asc(), ClaimRow.claim_id.asc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return [claim_from_row(r) for r in rows], int(total)


async def update_claim_verification(
    session: AsyncSession,
    tenant: TenantContext,
    claim_id: str,
    *,
    verification_status: str,
    trust_state: str | None = None,
    confidence: Decimal | None = None,
    supporting_claim_ids: list[UUID] | None = None,
    contradicting_claim_ids: list[UUID] | None = None,
) -> Claim:
    """Update mutable verification fields only — never evidence lineage."""
    row = await session.get(ClaimRow, claim_id)
    if row is None:
        raise KeyError(claim_id)
    tenant.assert_firm(row.firm_id)
    row.verification_status = verification_status
    if trust_state is not None:
        row.trust_state = trust_state
    if confidence is not None:
        row.confidence = confidence
    if supporting_claim_ids is not None:
        row.supporting_claim_ids = _uuids_to_str(supporting_claim_ids)
    if contradicting_claim_ids is not None:
        row.contradicting_claim_ids = _uuids_to_str(contradicting_claim_ids)
    row.updated_at = datetime.now(timezone.utc)
    await session.flush()
    return claim_from_row(row)
