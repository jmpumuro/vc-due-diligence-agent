# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""System readiness probes used by /health/ready and /system/status."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from thesis_api.settings import settings


async def check_postgres(session: AsyncSession) -> dict[str, Any]:
    try:
        await session.execute(text("SELECT 1"))
        vec = await session.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'"))
        has_vector = vec.scalar() is not None
        return {"ok": True, "vector": has_vector}
    except Exception as exc:  # noqa: BLE001 — surface as readiness failure
        return {"ok": False, "error": str(exc)}


async def check_searxng() -> dict[str, Any]:
    from thesis_api.services.search.searxng import SearxngAdapter

    adapter = SearxngAdapter(settings.searxng_url)
    health = await adapter.canary(firm_id="system")
    return {
        "ok": health.state == "ok",
        "json_enabled": health.json_enabled,
        "result_count": health.result_count,
        "last_canary_at": health.last_canary_at,
        "state": health.state,
        "engines_responding": health.engines_responding,
        "engines_failed": health.engines_failed,
        "from_cache": health.from_cache,
        "error": health.error,
    }


async def check_s3() -> dict[str, Any]:
    try:
        import boto3
        from botocore.client import Config

        client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        client.list_buckets()
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


async def check_temporal() -> dict[str, Any]:
    """TCP reachability for Stage 2; DescribeNamespace arrives with Stage 3 workers."""
    import asyncio
    import socket

    host, _, port_s = settings.temporal_host.partition(":")
    port = int(port_s or "7233")

    def _probe() -> bool:
        with socket.create_connection((host, port), timeout=3):
            return True

    try:
        ok = await asyncio.to_thread(_probe)
        return {"ok": ok}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


async def demo_workspace_state(session: AsyncSession) -> str:
    row = await session.execute(
        text("SELECT 1 FROM seed_markers WHERE name = 'demo_workspace' LIMIT 1")
    )
    return "ready" if row.scalar() else "missing"


async def check_worker_docs() -> dict[str, Any]:
    import httpx

    url = settings.worker_docs_url.rstrip("/") + "/health"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            res = await client.get(url)
            body = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
            ok = res.status_code == 200 and bool(body.get("ok"))
            return {
                "ok": ok,
                "status": body.get("status") if ok else "unavailable",
                "tesseract": body.get("tesseract"),
                "ocr_endpoint": body.get("ocr_endpoint"),
                "error": None if ok else f"http_{res.status_code}",
            }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "status": "unavailable", "error": str(exc)[:200]}


async def system_status(session: AsyncSession) -> dict[str, Any]:
    from thesis_api.services.clamav import ping_clamav
    from thesis_api.services.setup import is_setup_complete
    from thesis_api.services.worker_docs import harness_self_test

    pg = await check_postgres(session)
    search = await check_searxng()
    s3 = await check_s3()
    temporal = await check_temporal()
    clam = await ping_clamav()
    docs = await check_worker_docs()
    harness = await harness_self_test() if docs.get("ok") else {"ok": False, "error": "worker_docs_down"}
    demo = await demo_workspace_state(session) if settings.demo_workspace else "disabled"
    has_key = bool(settings.openai_api_key.strip())
    setup_done = await is_setup_complete(session) or settings.setup_complete

    from thesis_api.services.llm_gateway import provider_health
    from thesis_api.services.sanctions.ofac import dataset_status, load_dataset

    provider = await provider_health() if has_key else {"state": "missing_key", "models": [], "model": None}
    if not has_key:
        # Still surface local-route probe when no OpenAI key.
        provider = await provider_health()

    try:
        _entries, ofac_meta = await load_dataset(prefer_live=False)
        ofac = dataset_status(ofac_meta)
    except Exception as exc:  # noqa: BLE001
        ofac = {"status": "unavailable", "error": str(exc)[:200]}

    if not setup_done and demo != "ready":
        mode = "setup_required"
    elif demo == "ready" and not has_key:
        mode = "demo_ready"
    elif has_key and pg["ok"] and search.get("state") == "ok":
        mode = "live_ready"
    elif has_key:
        mode = "degraded"
    elif not setup_done:
        mode = "setup_required"
    else:
        mode = "demo_ready" if demo == "ready" else "setup_required"

    upload_enabled = bool(clam.get("ok"))
    parse_available = bool(docs.get("ok") and harness.get("ok"))
    return {
        "mode": mode,
        "setup_complete": setup_done,
        "demo_workspace": demo,
        "search": {
            "state": search.get("state", "unavailable"),
            "json_enabled": search.get("json_enabled", False),
            "last_canary_at": search.get("last_canary_at"),
            "result_count": search.get("result_count", 0),
            "engines_responding": search.get("engines_responding") or [],
            "engines_failed": search.get("engines_failed") or [],
            "error": search.get("error"),
        },
        "provider": provider,
        "ofac": ofac,
        "dependencies": {
            "postgres": pg,
            "object_store": s3,
            "temporal": temporal,
            "searxng": {
                "ok": search.get("ok", False),
                "state": search.get("state"),
                "engines_failed": search.get("engines_failed") or [],
            },
            "clamav": clam,
            "worker_docs": docs,
        },
        "private_pipeline": {
            "upload_enabled": upload_enabled,
            "clamav": bool(clam.get("ok")),
            "ocr_verified": bool(settings.ocr_product_verified),
            "ocr_parse_available": parse_available,
            "q_docs": True,
            "worker_docs": bool(docs.get("ok")),
            "tesseract": docs.get("tesseract"),
            "harness_self_test": harness,
            "level3_screening": bool(settings.ocr_product_verified),
            "notice": (
                (
                    "OCR_PRODUCT_VERIFIED on — L3 public screening + ClamAV uploads + q.docs "
                    "parse enabled. Private-document AI stays off (D1)."
                )
                if settings.ocr_product_verified
                else (
                    "ClamAV + worker-docs + q.docs worker path online; set OCR_PRODUCT_VERIFIED after D4 product smoke."
                    if upload_enabled and parse_available
                    else (
                        "ClamAV scans uploads; worker-docs health only — harness self-test not green."
                        if upload_enabled and docs.get("ok")
                        else "Waiting for ClamAV and/or worker-docs health."
                    )
                )
            ),
        },
    }


async def health_ready(session: AsyncSession) -> tuple[bool, dict[str, Any]]:
    status = await system_status(session)
    deps = status["dependencies"]
    # SearXNG canary may fail offline; Stage 2 readiness requires postgres + migrate tables.
    ok = bool(deps["postgres"].get("ok"))
    return ok, status
