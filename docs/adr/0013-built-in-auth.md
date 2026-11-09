# ADR-013: Built-in authentication

- Status: Accepted
- Date: 2026-11-07

## Decision

First-run `/setup` creates a local owner account. Built-in local accounts are the default; OIDC is optional. Demo workspace is browsable with a seeded demo user through the real API.

## Consequences

No mandatory IdP. Session carries firm and roles; the UI never trusts URL or localStorage for authz.
