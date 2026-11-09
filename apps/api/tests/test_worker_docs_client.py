"""worker-docs client unit behaviour (no live service required)."""

from __future__ import annotations

import asyncio

import httpx

from thesis_api.services import worker_docs


def test_parse_pdf_transport_error(monkeypatch) -> None:
    async def boom(*_a, **_k):
        raise httpx.ConnectError("refused")

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            return await boom()

    monkeypatch.setattr(worker_docs.httpx, "AsyncClient", FakeClient)
    out = asyncio.run(worker_docs.parse_pdf(b"%PDF-1.4", "x.pdf"))
    assert out["ok"] is False
    assert "refused" in out["error"]
