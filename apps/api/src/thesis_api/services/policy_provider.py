# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""PolicyEnforcedProvider — REM-P0-01 / D1.

The only path that may construct a model client. Private segments are denied by
default until a workspace policy explicitly authorizes categories + purposes,
or a verified local route is configured.
"""

from __future__ import annotations

from typing import Any, Protocol

from thesis_contracts.security import (
    ModelRequestEnvelope,
    PolicyDecision,
)


class ExternalAINotAuthorized(PermissionError):
    """Mapped to tool/API error EXTERNAL_AI_NOT_AUTHORIZED."""


class ModelClient(Protocol):
    async def complete(self, *, prompt: str, **kwargs: Any) -> str: ...


class _DeniedClient:
    """Never used for completions — present only to keep type surface closed."""

    async def complete(self, *, prompt: str, **kwargs: Any) -> str:
        raise ExternalAINotAuthorized("model client denied")


class PolicyEnforcedProvider:
    """Fail-closed gate in front of any LLM or embedding call."""

    def __init__(self, *, external_enabled: bool = False, local_route_available: bool = False):
        self._external_enabled = external_enabled
        self._local_route_available = local_route_available
        # category → purposes authorized for external transmission (empty = none)
        self._external_allow: dict[str, set[str]] = {}
        self._clients: dict[str, ModelClient] = {}

    def register_route_client(self, route: str, client: ModelClient) -> None:
        """Register an already-constructed client for an authorized route only."""
        if route not in {"external", "local"}:
            raise ValueError(f"unknown route: {route}")
        self._clients[route] = client

    def authorize_external_category(self, category: str, *purposes: str) -> None:
        self._external_allow.setdefault(category, set()).update(purposes)

    def decide(self, envelope: ModelRequestEnvelope) -> PolicyDecision:
        private = [s for s in envelope.segments if s.scope == "private"]
        if not private:
            return PolicyDecision(
                allowed=True,
                route="external" if self._external_enabled else "local",
                policy_version=1,
                reason=None,
            )

        # Private path: prefer local; external only if every category/purpose allowed.
        if self._local_route_available:
            return PolicyDecision(
                allowed=True, route="local", policy_version=1, reason=None
            )

        if not self._external_enabled:
            return PolicyDecision(
                allowed=False,
                route="denied",
                policy_version=1,
                reason="external AI disabled for private data (D1 default)",
            )

        missing: list[str] = []
        for seg in private:
            cat = seg.category or ""
            allowed_purposes = self._external_allow.get(cat, set())
            if envelope.purpose not in allowed_purposes:
                missing.append(f"{cat}:{envelope.purpose}")
        if missing:
            return PolicyDecision(
                allowed=False,
                route="denied",
                policy_version=1,
                reason=f"category/purpose not allowed: {', '.join(missing)}",
            )
        return PolicyDecision(allowed=True, route="external", policy_version=1, reason=None)

    def authorize_or_raise(self, envelope: ModelRequestEnvelope) -> PolicyDecision:
        decision = self.decide(envelope)
        if not decision.allowed:
            raise ExternalAINotAuthorized(decision.reason or "denied")
        return decision

    def client_for(self, envelope: ModelRequestEnvelope) -> ModelClient:
        """Sole construction/selection path for model clients (D1)."""
        decision = self.authorize_or_raise(envelope)
        route = decision.route
        if route == "denied":
            raise ExternalAINotAuthorized(decision.reason or "denied")
        client = self._clients.get(route)
        if client is None:
            # Fail closed: never invent an OpenAI/local client here.
            raise ExternalAINotAuthorized(
                f"no registered client for route={route}; "
                "configure PolicyEnforcedProvider.register_route_client"
            )
        return client
