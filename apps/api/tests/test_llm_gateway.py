"""LLM gateway + D1 public path unit tests (no live network)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from thesis_api.services.llm_gateway import build_provider, workspace_uuid
from thesis_api.services.policy_provider import ExternalAINotAuthorized
from thesis_contracts.security import ModelInputSegment, ModelRequestEnvelope


def test_workspace_uuid_stable() -> None:
    assert workspace_uuid("frm_demo") == workspace_uuid("frm_demo")
    assert workspace_uuid("frm_demo") != workspace_uuid("frm_other")


def test_build_provider_without_key_denies_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("thesis_api.services.llm_gateway.settings.openai_api_key", "")
    provider = build_provider()
    envelope = ModelRequestEnvelope(
        workspace_id=uuid4(),
        purpose="summarize_section",
        segments=[ModelInputSegment(text="public", scope="public")],
        operation_id=uuid4(),
    )
    # No external client registered when key missing and route may be local/denied.
    with pytest.raises(ExternalAINotAuthorized):
        provider.client_for(envelope)


def test_build_provider_with_key_registers_external(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "thesis_api.services.llm_gateway.settings.openai_api_key", "sk-test-not-real"
    )
    monkeypatch.setattr("thesis_api.services.llm_gateway.settings.openai_model", "gpt-4o-mini")
    provider = build_provider()
    envelope = ModelRequestEnvelope(
        workspace_id=uuid4(),
        purpose="extract_claims",
        segments=[ModelInputSegment(text="Acme has a public website", scope="public")],
        operation_id=uuid4(),
    )
    client = provider.client_for(envelope)
    assert hasattr(client, "complete")


def test_private_never_silently_uses_openai(monkeypatch: pytest.MonkeyPatch) -> None:
    """REM-P1-05 / D1: OPENAI_API_KEY alone must not authorize private segments."""
    monkeypatch.setattr(
        "thesis_api.services.llm_gateway.settings.openai_api_key", "sk-test-not-real"
    )
    monkeypatch.setattr("thesis_api.services.llm_gateway.settings.local_llm_url", "")
    provider = build_provider(local_route_available=False)
    envelope = ModelRequestEnvelope(
        workspace_id=uuid4(),
        assessment_id=uuid4(),
        revision=1,
        purpose="extract_claims",
        segments=[
            ModelInputSegment(
                text="confidential P&L",
                scope="private",
                category="document_tables",
                document_id=uuid4(),
                document_version=1,
            )
        ],
        operation_id=uuid4(),
    )
    with pytest.raises(ExternalAINotAuthorized):
        provider.client_for(envelope)
