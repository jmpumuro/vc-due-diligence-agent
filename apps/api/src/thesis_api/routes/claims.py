"""Claims and contradictions API — tenant-scoped, paginated."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from thesis_api.db.models import AssessmentRow
from thesis_api.db.session import get_session
from thesis_api.deps import get_tenant
from thesis_api.services.claims_store import (
    ClaimLineageImmutableError,
    get_claim,
    insert_claim,
    list_claims,
    update_claim_verification,
)
from thesis_api.services.contradictions_store import (
    VersionConflictError,
    get_contradiction,
    insert_contradiction,
    list_contradictions,
    list_resolution_history,
    resolve_contradiction,
)
from thesis_api.tenant import TenantContext, TenantIsolationError
from thesis_contracts.research import Claim, ContradictionRecord

router = APIRouter(tags=["claims"])


class ClaimCreateBody(BaseModel):
    claim: Claim


class ClaimVerificationBody(BaseModel):
    verification_status: Literal[
        "extracted", "verified", "contested", "rejected", "insufficient"
    ]
    trust_state: Literal["supported", "contested", "unsupported", "stale", "insufficient"] | None = (
        None
    )
    confidence: Decimal | None = Field(default=None, ge=0, le=1)
    supporting_claim_ids: list[UUID] | None = None
    contradicting_claim_ids: list[UUID] | None = None


class ContradictionCreateBody(BaseModel):
    contradiction: ContradictionRecord


class ContradictionResolveBody(BaseModel):
    expected_version: int = Field(ge=1)
    resolution: Literal["open", "accepted_risk", "resolved_with_private", "waived"]
    comment: str | None = None
    human_review_state: Literal["none", "pending", "in_review", "decided"] = "decided"


async def _load_assessment(
    session: AsyncSession, tenant: TenantContext, assessment_id: str
) -> AssessmentRow:
    row = (
        await session.execute(select(AssessmentRow).where(AssessmentRow.id == assessment_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    try:
        tenant.assert_firm(row.firm_id)
    except TenantIsolationError as exc:
        raise HTTPException(status_code=404, detail="NOT_FOUND") from exc
    return row


@router.get("/assessments/{assessment_id}/claims")
async def list_assessment_claims(
    assessment_id: str,
    domain_id: str | None = None,
    verification_status: str | None = None,
    revision: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    await _load_assessment(session, tenant, assessment_id)
    items, total = await list_claims(
        session,
        tenant,
        assessment_id=assessment_id,
        domain_id=domain_id,
        verification_status=verification_status,
        revision=revision,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [c.model_dump(mode="json") for c in items],
        "total": total,
        "limit": limit,
        "offset": offset,
        "next_offset": offset + limit if offset + limit < total else None,
    }


@router.get("/claims/{claim_id}")
async def get_claim_endpoint(
    claim_id: str,
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    try:
        claim = await get_claim(session, tenant, claim_id)
    except TenantIsolationError as exc:
        raise HTTPException(status_code=404, detail="NOT_FOUND") from exc
    if claim is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return claim.model_dump(mode="json")


@router.post("/assessments/{assessment_id}/claims", status_code=201)
async def create_claim(
    assessment_id: str,
    body: ClaimCreateBody,
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    await _load_assessment(session, tenant, assessment_id)
    if str(body.claim.assessment_id) != assessment_id:
        raise HTTPException(status_code=400, detail="ASSESSMENT_MISMATCH")
    try:
        stored = await insert_claim(session, tenant, body.claim)
        await session.commit()
    except ClaimLineageImmutableError as exc:
        raise HTTPException(status_code=409, detail="LINEAGE_IMMUTABLE") from exc
    except TenantIsolationError as exc:
        raise HTTPException(status_code=403, detail="FORBIDDEN") from exc
    return stored.model_dump(mode="json")


@router.patch("/claims/{claim_id}/verification")
async def patch_claim_verification(
    claim_id: str,
    body: ClaimVerificationBody,
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    try:
        updated = await update_claim_verification(
            session,
            tenant,
            claim_id,
            verification_status=body.verification_status,
            trust_state=body.trust_state,
            confidence=body.confidence,
            supporting_claim_ids=body.supporting_claim_ids,
            contradicting_claim_ids=body.contradicting_claim_ids,
        )
        await session.commit()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="NOT_FOUND") from exc
    except TenantIsolationError as exc:
        raise HTTPException(status_code=404, detail="NOT_FOUND") from exc
    return updated.model_dump(mode="json")


@router.get("/assessments/{assessment_id}/contradictions")
async def list_assessment_contradictions(
    assessment_id: str,
    resolution: str | None = None,
    revision: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    await _load_assessment(session, tenant, assessment_id)
    items, total = await list_contradictions(
        session,
        tenant,
        assessment_id=assessment_id,
        resolution=resolution,
        revision=revision,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [c.model_dump(mode="json") for c in items],
        "total": total,
        "limit": limit,
        "offset": offset,
        "next_offset": offset + limit if offset + limit < total else None,
    }


@router.get("/contradictions/{contradiction_id}")
async def get_contradiction_endpoint(
    contradiction_id: str,
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    try:
        rec = await get_contradiction(session, tenant, contradiction_id)
    except TenantIsolationError as exc:
        raise HTTPException(status_code=404, detail="NOT_FOUND") from exc
    if rec is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return rec.model_dump(mode="json")


@router.post("/assessments/{assessment_id}/contradictions", status_code=201)
async def create_contradiction(
    assessment_id: str,
    body: ContradictionCreateBody,
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    await _load_assessment(session, tenant, assessment_id)
    if str(body.contradiction.assessment_id) != assessment_id:
        raise HTTPException(status_code=400, detail="ASSESSMENT_MISMATCH")
    try:
        stored = await insert_contradiction(session, tenant, body.contradiction)
        await session.commit()
    except TenantIsolationError as exc:
        raise HTTPException(status_code=403, detail="FORBIDDEN") from exc
    return stored.model_dump(mode="json")


@router.post("/contradictions/{contradiction_id}/resolve")
async def resolve_contradiction_endpoint(
    contradiction_id: str,
    body: ContradictionResolveBody,
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    try:
        updated = await resolve_contradiction(
            session,
            tenant,
            contradiction_id,
            expected_version=body.expected_version,
            new_resolution=body.resolution,
            comment=body.comment,
            human_review_state=body.human_review_state,
        )
        await session.commit()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="NOT_FOUND") from exc
    except TenantIsolationError as exc:
        raise HTTPException(status_code=404, detail="NOT_FOUND") from exc
    except VersionConflictError as exc:
        raise HTTPException(status_code=409, detail="VERSION_CONFLICT") from exc
    return updated.model_dump(mode="json")


@router.get("/contradictions/{contradiction_id}/history")
async def contradiction_history(
    contradiction_id: str,
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    try:
        events = await list_resolution_history(session, tenant, contradiction_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="NOT_FOUND") from exc
    except TenantIsolationError as exc:
        raise HTTPException(status_code=404, detail="NOT_FOUND") from exc
    return {"items": [e.model_dump(mode="json") for e in events]}
