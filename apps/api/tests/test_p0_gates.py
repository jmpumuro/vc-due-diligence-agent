"""Regression for REM-P0-01 and REM-P0-02 scaffolding."""

from __future__ import annotations

from uuid import uuid4

import pytest

from thesis_api.services.policy_provider import ExternalAINotAuthorized, PolicyEnforcedProvider
from thesis_api.tenant import TenantContext, TenantIsolationError
from thesis_contracts.security import ModelInputSegment, ModelRequestEnvelope


def test_tenant_firm_mismatch_raises() -> None:
    ctx = TenantContext(firm_id="frm_demo", user_id="u1", roles=("partner",))
    with pytest.raises(TenantIsolationError):
        ctx.assert_firm("frm_other")


def test_private_access_requires_deal_team() -> None:
    aid = str(uuid4())
    ctx = TenantContext(firm_id="frm_demo", user_id="u1", roles=("analyst",))
    assert not ctx.may_access_private(aid)
    ctx2 = TenantContext(
        firm_id="frm_demo",
        user_id="u1",
        roles=("partner",),
        deal_team_assessment_ids=frozenset({aid}),
    )
    assert ctx2.may_access_private(aid)


def test_d1_default_denies_private_external() -> None:
    provider = PolicyEnforcedProvider(external_enabled=False, local_route_available=False)
    envelope = ModelRequestEnvelope(
        workspace_id=uuid4(),
        assessment_id=uuid4(),
        revision=1,
        purpose="extract_claims",
        segments=[
            ModelInputSegment(
                text="secret table",
                scope="private",
                category="document_tables",
                document_id=uuid4(),
                document_version=1,
            )
        ],
        operation_id=uuid4(),
    )
    with pytest.raises(ExternalAINotAuthorized):
        provider.authorize_or_raise(envelope)


def test_d1_public_segments_allowed() -> None:
    provider = PolicyEnforcedProvider(external_enabled=True, local_route_available=False)
    envelope = ModelRequestEnvelope(
        workspace_id=uuid4(),
        purpose="summarize_section",
        segments=[ModelInputSegment(text="public page", scope="public")],
        operation_id=uuid4(),
    )
    decision = provider.authorize_or_raise(envelope)
    assert decision.allowed
    assert decision.route == "external"


def test_d1_client_for_requires_registered_route() -> None:
    provider = PolicyEnforcedProvider(external_enabled=True, local_route_available=False)
    envelope = ModelRequestEnvelope(
        workspace_id=uuid4(),
        purpose="summarize_section",
        segments=[ModelInputSegment(text="public page", scope="public")],
        operation_id=uuid4(),
    )
    with pytest.raises(ExternalAINotAuthorized, match="no registered client"):
        provider.client_for(envelope)


def test_d1_local_route_for_private_when_available() -> None:
    provider = PolicyEnforcedProvider(external_enabled=False, local_route_available=True)

    class _Local:
        async def complete(self, *, prompt: str, **kwargs: object) -> str:
            return "ok"

    provider.register_route_client("local", _Local())
    envelope = ModelRequestEnvelope(
        workspace_id=uuid4(),
        assessment_id=uuid4(),
        revision=1,
        purpose="extract_claims",
        segments=[
            ModelInputSegment(
                text="secret table",
                scope="private",
                category="document_tables",
                document_id=uuid4(),
                document_version=1,
            )
        ],
        operation_id=uuid4(),
    )
    client = provider.client_for(envelope)
    assert isinstance(client, _Local)
