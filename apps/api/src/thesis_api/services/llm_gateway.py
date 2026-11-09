"""Sole LLM entrypoint — always through PolicyEnforcedProvider (REM-P0-01 / D1)."""

from __future__ import annotations

from uuid import UUID, uuid4, uuid5, NAMESPACE_DNS

import httpx

from thesis_api.services.openai_chat import OpenAIChatClient
from thesis_api.services.policy_provider import ExternalAINotAuthorized, PolicyEnforcedProvider
from thesis_api.settings import settings
from thesis_contracts.security import ModelInputSegment, ModelRequestEnvelope

_FIRM_NS = uuid5(NAMESPACE_DNS, "thesis.firm")


def workspace_uuid(firm_id: str) -> UUID:
    return uuid5(_FIRM_NS, firm_id)


async def probe_local_llm(url: str | None = None) -> dict:
    """OpenAI-compatible /v1/models probe. http-echo stubs fail → local_route stays false."""
    base = (url if url is not None else settings.local_llm_url).rstrip("/")
    if not base:
        return {"ok": False, "reason": "LOCAL_LLM_URL unset"}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{base}/v1/models")
            if r.status_code != 200:
                return {"ok": False, "reason": f"status={r.status_code}", "url": base}
            body = r.json()
            if not isinstance(body, dict) or "data" not in body:
                return {"ok": False, "reason": "not_openai_compatible", "url": base}
            return {"ok": True, "url": base, "models": body.get("data") or []}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "reason": str(exc)[:200], "url": base}


def build_provider(*, local_route_available: bool | None = None) -> PolicyEnforcedProvider:
    """Build a provider with the external OpenAI client registered when a key is set.

    Private segments never silently use the external client unless categories are
    explicitly authorized. local_route_available defaults False; callers that have
    probed a real OpenAI-compatible local server may pass True.
    """
    key = settings.openai_api_key.strip()
    local_ok = False if local_route_available is None else local_route_available
    provider = PolicyEnforcedProvider(
        external_enabled=bool(key),
        local_route_available=local_ok,
    )
    if key:
        provider.register_route_client(
            "external",
            OpenAIChatClient(api_key=key, model=settings.openai_model),
        )
    if local_ok and settings.local_llm_url.strip():
        # Same OpenAI-compatible client against local base URL (no cloud key).
        provider.register_route_client(
            "local",
            OpenAIChatClient(
                api_key=settings.local_llm_api_key or "local",
                model=settings.local_llm_model or "local-model",
                base_url=settings.local_llm_url.rstrip("/") + "/v1",
            ),
        )
    return provider


async def build_provider_probed() -> PolicyEnforcedProvider:
    probe = await probe_local_llm()
    return build_provider(local_route_available=bool(probe.get("ok")))


async def public_complete(
    *,
    firm_id: str,
    purpose: str,
    prompt: str,
    assessment_id: UUID | None = None,
    revision: int | None = None,
    system: str | None = None,
    max_tokens: int = 400,
) -> str:
    """Run a public-only completion. Raises ExternalAINotAuthorized if denied/missing."""
    provider = build_provider()
    envelope = ModelRequestEnvelope(
        workspace_id=workspace_uuid(firm_id),
        assessment_id=assessment_id,
        revision=revision,
        purpose=purpose,  # type: ignore[arg-type]
        segments=[ModelInputSegment(text=prompt[:8000], scope="public")],
        operation_id=uuid4(),
    )
    client = provider.client_for(envelope)
    return await client.complete(prompt=prompt, system=system, max_tokens=max_tokens)


async def private_complete(
    *,
    firm_id: str,
    purpose: str,
    prompt: str,
    category: str,
    assessment_id: UUID | None = None,
    revision: int | None = None,
    document_id: UUID | None = None,
    document_version: int | None = None,
    system: str | None = None,
    max_tokens: int = 400,
) -> str:
    """Private-segment completion — never silently falls back to OpenAI.

    Requires a probed local route, or an explicit authorize_external_category
    (not applied here by default). With only OPENAI_API_KEY set, this raises.
    """
    provider = await build_provider_probed()
    envelope = ModelRequestEnvelope(
        workspace_id=workspace_uuid(firm_id),
        assessment_id=assessment_id,
        revision=revision,
        purpose=purpose,  # type: ignore[arg-type]
        segments=[
            ModelInputSegment(
                text=prompt[:8000],
                scope="private",
                category=category,  # type: ignore[arg-type]
                document_id=document_id,
                document_version=document_version,
            )
        ],
        operation_id=uuid4(),
    )
    # PolicyEnforcedProvider denies private→external unless categories authorized;
    # build_provider_probed never auto-authorizes. No silent OpenAI fallback.
    client = provider.client_for(envelope)
    return await client.complete(prompt=prompt, system=system, max_tokens=max_tokens)


async def provider_health() -> dict:
    key = settings.openai_api_key.strip()
    local = await probe_local_llm()
    out: dict = {
        "local_route": local,
        "local_route_available": bool(local.get("ok")),
        "private_silent_openai_fallback": False,
    }
    if not key:
        out.update({"state": "missing_key", "models": [], "model": None})
        return out
    client = OpenAIChatClient(api_key=key, model=settings.openai_model)
    try:
        models = await client.list_model_ids(limit=12)
        out.update(
            {
                "state": "configured",
                "models": models,
                "model": settings.openai_model,
                "configured_model_present": settings.openai_model in models
                or any(settings.openai_model in m for m in models),
            }
        )
        return out
    except Exception as exc:  # noqa: BLE001
        out.update(
            {
                "state": "error",
                "models": [],
                "model": settings.openai_model,
                "error": str(exc)[:300],
            }
        )
        return out


__all__ = [
    "ExternalAINotAuthorized",
    "build_provider",
    "build_provider_probed",
    "public_complete",
    "private_complete",
    "provider_health",
    "probe_local_llm",
    "workspace_uuid",
]
