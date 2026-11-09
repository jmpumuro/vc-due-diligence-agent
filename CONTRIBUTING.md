# Contributing

Thesis is Apache-2.0. Continue on this codebase — do not restart large subsystems without an ADR.

## Workflow

1. Read `docs/remediation-backlog.md` before features that touch private docs, storage, OFAC, OCR, or multi-tenant evidence.
2. Keep tests green: `uv sync && uv run pytest -q`
3. Run the licence gate: `uv run python scripts/licence_gate.py`
4. Prefer small, stage-aligned PRs (Stages 1–9 in `README.md`)

## Rules that stay in force

- Real integrations only (no MSW / fake `DEMO_MODE` network stubs)
- UI must load without an OpenAI key
- Never invent a D6 false-claims site URL
- Do not mark production-ready until Gate H / `VERIFICATION.md` passes
