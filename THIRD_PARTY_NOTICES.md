# Third-party notices

Aggregated from root `NOTICE` for REM-P1-06 / D5-02. This file does **not** invent
licence conclusions for transitive dependencies — verify at pin.

## First-party

Thesis is licensed under Apache-2.0. See `LICENSE` and `NOTICE`.

## Runtime / compose (selected)

| Component | Role | Licence note |
| --- | --- | --- |
| FastAPI, Starlette, Pydantic, SQLAlchemy, Alembic, HTTPX, Temporal Python SDK, Next.js | Application runtime | See each package's metadata (typically permissive). |
| SearXNG | Optional Compose search service | AGPL-3.0 — separate process; not vendored into this source tree. |
| SeaweedFS | Optional object store image | See upstream licence. |
| ClamAV (`clamav/clamav` image) | Optional malware scan service | See upstream / image licence. |
| Tesseract OCR | Optional `worker-docs` image | Apache-2.0 (engine); confirm distribution terms for language data. |

## Pattern sources (ideas / clean-room unless noted)

- GPT-Researcher and II-Researcher (Apache-2.0)
- Agent Search (MIT)
- FirstSignal: ideas only — no licence; no source copied

Full dependency SPDX reuse audit remains open under REM-P1-06.
