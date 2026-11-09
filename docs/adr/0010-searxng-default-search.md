# ADR-010: SearXNG as default search

- Status: Accepted
- Date: 2026-11-07

## Decision

Self-hosted SearXNG is the default web search provider. It starts with `docker compose up --build`. No third-party search account is required. Paid providers (Tavily, Brave, Exa, OpenAI hosted search) are opt-in adapters only.

## Consequences

Compose includes SearXNG; readiness includes a canary search, not only container health. JSON format must be enabled in settings.
