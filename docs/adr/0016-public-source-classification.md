# ADR-016: Public-source classification

- Status: Accepted
- Date: 2026-11-07

## Decision

Snapshot *content* of public pages is `public` and may be stored once and referenced by many tenants. The record that a tenant searched or fetched a URL is `tenant_private`. Private document text never enters search queries or external requests without D1 authorization.

## Consequences

Caches for search are keyed by firm. Evidence spans for private docs are deal-team scoped.
