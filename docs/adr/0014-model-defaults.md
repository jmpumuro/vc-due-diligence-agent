# ADR-014: Model defaults and startup verification

- Status: Accepted
- Date: 2026-11-07

## Decision

OpenAI via the official SDK is the default LLM provider. Proposed model IDs are verified against the account’s model list at startup. A missing key must not prevent the UI from loading; live work returns `PROVIDER_NOT_CONFIGURED` until configured.

## Consequences

Only `PolicyEnforcedProvider` constructs a model client (D1). Model IDs in config are proposals until verified.
