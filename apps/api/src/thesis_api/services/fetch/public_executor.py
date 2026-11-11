"""Trusted public research boundary, independent of storage and model clients.

Only this bounded result crosses back from an executor. A future sandbox adapter
must pass the same validation; it cannot select a tenant or write evidence.
"""

from __future__ import annotations

import hashlib

from thesis_contracts.public_fetch import PublicFetchRequest, PublicFetchResult

from thesis_api.services.fetch.safe_fetcher import (
    SafeFetchError,
    _content_type_allowed,
    safe_fetch,
    validate_url,
)


def validate_public_result(
    request: PublicFetchRequest, result: PublicFetchResult
) -> PublicFetchResult:
    # Revalidate even if constructed by another Python component without validation.
    result = PublicFetchResult.model_validate(result.model_dump())
    if result.requested_url != validate_url(request.url):
        raise SafeFetchError("RESULT_REQUEST_MISMATCH", "unexpected requested URL")
    if len(result.body) > request.max_bytes:
        raise SafeFetchError("RESPONSE_TOO_LARGE", "executor exceeded request limit")
    if not _content_type_allowed(result.content_type):
        raise SafeFetchError("CONTENT_TYPE_BLOCKED", "unexpected executor content type")
    for url in result.hops:
        validate_url(url)
    return result


async def execute_public_fetch(request: PublicFetchRequest) -> PublicFetchResult:
    from thesis_api.settings import settings

    if settings.research_execution_backend == "opensandbox":
        from thesis_api.services.fetch.sandbox_executor import get_executor

        return await get_executor().fetch(request)
    result = await safe_fetch(request.url, max_bytes=request.max_bytes)
    return validate_public_result(
        request,
        PublicFetchResult(
            requested_url=result.hops[0],
            final_url=result.final_url,
            status_code=result.status_code,
            content_type=result.content_type,
            body=result.body,
            body_sha256=hashlib.sha256(result.body).hexdigest(),
            hops=result.hops,
        ),
    )
