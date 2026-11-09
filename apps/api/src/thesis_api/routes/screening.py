"""Start Level 1–3 company screening workflows."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client
from temporalio.exceptions import WorkflowAlreadyStartedError

from thesis_api.db.models import AssessmentRow
from thesis_api.db.models_stage6 import DataRoomRow, DealTeamMemberRow
from thesis_api.db.session import get_session
from thesis_api.deps import get_tenant
from thesis_api.services.level_gates import level3_screening_allowed
from thesis_api.settings import settings
from thesis_api.tenant import TenantContext, TenantIsolationError
from thesis_api.temporal_app.workflows import CompanyScreeningWorkflow

router = APIRouter(tags=["screening"])


class CreateAssessmentBody(BaseModel):
    company_name: str = Field(min_length=1, max_length=255)
    level: int = Field(default=1, ge=1, le=3)
    start_screening: bool = True
    website: str | None = Field(default=None, max_length=512)


class ScreenBody(BaseModel):
    level: int | None = Field(default=None, ge=1, le=3)


class DeepenBody(BaseModel):
    target_level: int = Field(ge=2, le=3)
    start_screening: bool = True


async def _start_workflow(
    *,
    firm_id: str,
    user_id: str,
    assessment_id: str,
    company_name: str,
    level: int,
    revision: int,
    prior_workflow_id: str | None = None,
) -> str:
    from thesis_api.services.workflow_reconcile import terminate_workflow

    if prior_workflow_id and prior_workflow_id != f"screen:{firm_id}:{assessment_id}:r{revision}":
        await terminate_workflow(
            prior_workflow_id,
            reason=f"superseded by revision {revision}",
        )

    client = await Client.connect(settings.temporal_host)
    # Include revision so deepen / re-run never collide with a prior workflow id.
    workflow_id = f"screen:{firm_id}:{assessment_id}:r{revision}"
    try:
        await client.start_workflow(
            CompanyScreeningWorkflow.run,
            {
                "firm_id": firm_id,
                "user_id": user_id,
                "assessment_id": assessment_id,
                "company_name": company_name,
                "level": level,
                "revision": revision,
            },
            id=workflow_id,
            task_queue="q.system",
        )
    except WorkflowAlreadyStartedError:
        # Idempotent retry of the same revision.
        pass
    return workflow_id


async def _ensure_l3_shell(
    session: AsyncSession,
    *,
    tenant: TenantContext,
    assessment_id: str,
) -> str:
    """Ensure deal-team membership + open data-room row; return data_room_id."""
    existing_member = (
        await session.execute(
            select(DealTeamMemberRow).where(
                DealTeamMemberRow.assessment_id == assessment_id,
                DealTeamMemberRow.user_id == tenant.user_id,
            )
        )
    ).scalar_one_or_none()
    if existing_member is None:
        session.add(
            DealTeamMemberRow(
                id=str(uuid4()),
                firm_id=tenant.firm_id,
                assessment_id=assessment_id,
                user_id=tenant.user_id,
                role="lead",
            )
        )

    room = (
        await session.execute(
            select(DataRoomRow).where(DataRoomRow.assessment_id == assessment_id)
        )
    ).scalar_one_or_none()
    if room is None:
        data_room_id = str(uuid4())
        session.add(
            DataRoomRow(
                data_room_id=data_room_id,
                firm_id=tenant.firm_id,
                assessment_id=assessment_id,
                status="open",
                object_prefix=f"{tenant.firm_id}/{assessment_id}/",
                legal_hold=False,
            )
        )
        return data_room_id
    return room.data_room_id


def _l3_notice(*, screening_started: bool) -> str:
    if screening_started:
        return (
            "Level 3 public screening started (all domains including financials from "
            "public sources). Uploads are ClamAV-gated; OCR/parse via worker-docs + q.docs. "
            "Private-document AI stays off (D1)."
        )
    return (
        "Level 3 shell created. Uploads ClamAV-gated when scanner is healthy. "
        "Set OCR_PRODUCT_VERIFIED after D4 smoke to enable L3 public screening; "
        "private-document AI stays off (D1)."
    )


@router.post("/assessments", status_code=201)
async def create_assessment(
    body: CreateAssessmentBody,
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    if body.level == 3:
        if not any(r in tenant.roles for r in ("partner", "admin", "owner")):
            raise HTTPException(status_code=403, detail="LEVEL_NOT_ALLOWED")
        if body.start_screening and not level3_screening_allowed():
            raise HTTPException(
                status_code=409,
                detail="LEVEL3_PRIVATE_PIPELINE_NOT_READY",
            )

    aid = str(uuid4())
    summary: dict = {"headline": body.company_name}
    website = (body.website or "").strip()
    if website:
        if "://" not in website:
            website = f"https://{website}"
        summary["website"] = website
        summary["primary_domain"] = website
    row = AssessmentRow(
        id=aid,
        firm_id=tenant.firm_id,
        company_name=body.company_name,
        level=body.level,
        state="CREATED",
        revision=1,
        summary_json=summary,
    )
    session.add(row)
    await session.flush()

    data_room_id = None
    if body.level == 3:
        data_room_id = await _ensure_l3_shell(session, tenant=tenant, assessment_id=aid)

    workflow_id = None
    can_screen = body.start_screening and (
        body.level <= 2 or (body.level == 3 and level3_screening_allowed())
    )
    if can_screen:
        try:
            workflow_id = await _start_workflow(
                firm_id=tenant.firm_id,
                user_id=tenant.user_id,
                assessment_id=aid,
                company_name=body.company_name,
                level=body.level,
                revision=row.revision,
            )
            row.workflow_id = workflow_id
        except Exception as exc:  # noqa: BLE001
            await session.commit()
            raise HTTPException(
                status_code=503,
                detail=f"ASSESSMENT_CREATED_WORKFLOW_UNAVAILABLE: {exc}",
            ) from exc

    await session.commit()
    upload_enabled = False
    if body.level == 3:
        from thesis_api.services.clamav import ping_clamav

        upload_enabled = bool((await ping_clamav()).get("ok"))
    return {
        "assessment_id": aid,
        "firm_id": tenant.firm_id,
        "company_name": body.company_name,
        "level": body.level,
        "state": row.state,
        "workflow_id": workflow_id,
        "data_room_id": data_room_id,
        "upload_enabled": upload_enabled,
        "private_ai": "off",
        "level3_screening": level3_screening_allowed() if body.level == 3 else None,
        "notice": (
            _l3_notice(screening_started=bool(workflow_id)) if body.level == 3 else None
        ),
    }


@router.post("/assessments/{assessment_id}/screen")
async def start_screen(
    assessment_id: str,
    body: ScreenBody | None = None,
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    row = (
        await session.execute(select(AssessmentRow).where(AssessmentRow.id == assessment_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    try:
        tenant.assert_firm(row.firm_id)
    except TenantIsolationError as exc:
        raise HTTPException(status_code=404, detail="NOT_FOUND") from exc

    level = (body.level if body and body.level else row.level) or 1
    if level == 3 and not level3_screening_allowed():
        raise HTTPException(
            status_code=409,
            detail="LEVEL3_PRIVATE_PIPELINE_NOT_READY",
        )
    if row.state not in ("CREATED", "INFORMATION_REQUESTED", "FAILED"):
        raise HTTPException(status_code=409, detail=f"INVALID_STATE:{row.state}")

    prior = row.workflow_id
    try:
        workflow_id = await _start_workflow(
            firm_id=tenant.firm_id,
            user_id=tenant.user_id,
            assessment_id=row.id,
            company_name=row.company_name,
            level=level,
            revision=row.revision,
            prior_workflow_id=prior,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"WORKFLOW_START_FAILED: {exc}") from exc

    row.workflow_id = workflow_id
    row.level = level
    await session.commit()
    return {"assessment_id": row.id, "workflow_id": workflow_id, "level": level}


@router.post("/assessments/{assessment_id}/deepen")
async def deepen_assessment(
    assessment_id: str,
    body: DeepenBody,
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(get_tenant),
) -> dict:
    """Raise level in place and optionally start the deeper public screen."""
    row = (
        await session.execute(select(AssessmentRow).where(AssessmentRow.id == assessment_id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    try:
        tenant.assert_firm(row.firm_id)
    except TenantIsolationError as exc:
        raise HTTPException(status_code=404, detail="NOT_FOUND") from exc

    if body.target_level <= row.level:
        raise HTTPException(status_code=409, detail="ALREADY_AT_OR_ABOVE_LEVEL")
    if row.state in ("RESEARCHING", "PLANNING", "VALIDATING", "EVALUATING", "CRITIQUING"):
        raise HTTPException(status_code=409, detail=f"INVALID_STATE:{row.state}")

    if body.target_level == 3:
        if not any(r in tenant.roles for r in ("partner", "admin", "owner")):
            raise HTTPException(status_code=403, detail="LEVEL_NOT_ALLOWED")
        if body.start_screening and not level3_screening_allowed():
            raise HTTPException(
                status_code=409,
                detail="LEVEL3_PRIVATE_PIPELINE_NOT_READY",
            )

    data_room_id = None
    if body.target_level == 3:
        data_room_id = await _ensure_l3_shell(
            session, tenant=tenant, assessment_id=row.id
        )

    prior = row.workflow_id
    row.level = body.target_level
    row.revision = int(row.revision or 1) + 1
    row.state = "CREATED"
    summary = dict(row.summary_json or {})
    summary["level"] = body.target_level
    summary["deepened_from_revision"] = row.revision - 1
    row.summary_json = summary

    workflow_id = None
    can_screen = body.start_screening and (
        body.target_level <= 2
        or (body.target_level == 3 and level3_screening_allowed())
    )
    if can_screen:
        try:
            workflow_id = await _start_workflow(
                firm_id=tenant.firm_id,
                user_id=tenant.user_id,
                assessment_id=row.id,
                company_name=row.company_name,
                level=body.target_level,
                revision=row.revision,
                prior_workflow_id=prior,
            )
            row.workflow_id = workflow_id
        except Exception as exc:  # noqa: BLE001
            await session.commit()
            raise HTTPException(
                status_code=503,
                detail=f"DEEPEN_WORKFLOW_UNAVAILABLE: {exc}",
            ) from exc

    await session.commit()
    return {
        "assessment_id": row.id,
        "company_name": row.company_name,
        "level": row.level,
        "revision": row.revision,
        "state": row.state,
        "workflow_id": workflow_id,
        "data_room_id": data_room_id,
        "private_ai": "off",
        "level3_screening": level3_screening_allowed() if row.level == 3 else None,
        "notice": (
            _l3_notice(screening_started=bool(workflow_id)) if row.level == 3 else None
        ),
    }
