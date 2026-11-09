# ADR-017: Default object store (blocker B1)

- Status: Proposed (owner confirmation requested)
- Date: 2026-11-07

## Context

MinIO’s upstream repo was archived (2026-04-25); official images are no longer published. The S3 API abstraction stays either way.

## Decision (interim for Stage 2)

Default Compose object store is **SeaweedFS** (Apache-2.0) behind the S3-compatible API, pending an S3 compatibility run (versioning, lifecycle, SSE, multipart). MinIO remains a documented alternative if the firm pins its own image.

## Consequences

Stage 2 Compose uses SeaweedFS. If the owner rejects this, swap the Compose service only — application code talks S3.
