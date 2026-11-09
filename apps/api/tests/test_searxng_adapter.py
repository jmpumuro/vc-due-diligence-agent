# SPDX-License-Identifier: Apache-2.0
"""SearXNG adapter degrade thresholds + canary fallback (mocked HTTP)."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from thesis_api.services.search.searxng import SearxngAdapter


class _Resp:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=None)  # type: ignore[arg-type]

    def json(self) -> dict:
        return self._payload


@pytest.mark.parametrize(
    "count,failed,expected",
    [
        (0, ["brave"], "degraded"),
        (1, [], "degraded"),
        (3, [], "ok"),
    ],
)
def test_search_state_thresholds(monkeypatch: pytest.MonkeyPatch, count: int, failed: list, expected: str) -> None:
    adapter = SearxngAdapter("http://searxng.test", min_ok_results=3)

    async def fake_get(self, url, params=None):  # noqa: ANN001
        results = [
            {"url": f"https://example.com/{i}", "title": str(i), "engine": "wikipedia"}
            for i in range(count)
        ]
        return _Resp(200, {"results": results, "unresponsive_engines": failed})

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None):
            return await fake_get(self, url, params)

    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    out = asyncio.run(adapter.search(firm_id="f", query="q"))
    assert out["state"] == expected
    assert out["result_count"] == count
