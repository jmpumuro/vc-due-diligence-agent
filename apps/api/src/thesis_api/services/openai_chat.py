"""OpenAI Chat Completions client — constructed only via PolicyEnforcedProvider."""

from __future__ import annotations

from typing import Any

import httpx


class OpenAIChatClient:
    """Minimal cost-capped chat client (public segments only at call sites)."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-4o-mini",
        base_url: str = "https://api.openai.com/v1",
        timeout_s: float = 45.0,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s

    @property
    def model(self) -> str:
        return self._model

    async def complete(self, *, prompt: str, **kwargs: Any) -> str:
        system = str(kwargs.get("system") or "You are a VC diligence research assistant.")
        max_tokens = int(kwargs.get("max_tokens") or 400)
        temperature = float(kwargs.get("temperature") or 0.2)
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            res = await client.post(
                f"{self._base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                },
            )
            res.raise_for_status()
            data = res.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("OpenAI returned no choices")
        content = (choices[0].get("message") or {}).get("content") or ""
        return str(content).strip()

    async def list_model_ids(self, *, limit: int = 20) -> list[str]:
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            res = await client.get(
                f"{self._base_url}/models",
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            res.raise_for_status()
            data = res.json()
        ids = [str(m.get("id")) for m in data.get("data") or [] if m.get("id")]
        return ids[: max(1, min(limit, 50))]
