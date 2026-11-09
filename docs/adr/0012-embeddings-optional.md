# ADR-012: Embeddings optional

- Status: Accepted
- Date: 2026-11-07

## Decision

pgvector is always present. Embeddings are on in live mode when an OpenAI key exists; the demo workspace uses seeded vectors; full-text search is the fallback. Private spans use embeddings only via an allowed private route (D1).

## Consequences

Missing embeddings never block UI or Level 1/2 public research. Document lookup degrades to FTS.
