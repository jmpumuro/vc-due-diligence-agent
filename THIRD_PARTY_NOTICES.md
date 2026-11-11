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
| OpenSandbox SDK/server 1.2.0 | Optional public-research execution | Apache-2.0; installed packages, not vendored source. Server/SDK dependencies are locked separately. |
| OpenSandbox execd v1.1.0 / egress v1.1.7 | Optional execution and credential proxy | Apache-2.0 upstream project; exact image digests are pinned in `infra/opensandbox/server.toml`. |
| Playwright 1.58.0 | Optional Chromium automation | Apache-2.0; Chromium and OS packages retain their own notices in the built image. |

The Chromium seccomp profile is downloaded from Microsoft Playwright's v1.58.0
source and checked against a fixed SHA-256 by `infra/opensandbox/prepare.py`.
It is not vendored in this repository. Upstream source and licence:
https://github.com/microsoft/playwright/tree/v1.58.0 (Apache-2.0).
Research-image Python dependencies and control-plane dependencies use separate
hashed requirement locks. These pins do not close the existing project-wide
licence audit or imply image signing/provenance verification.

## Pattern sources (ideas / clean-room unless noted)

- GPT-Researcher and II-Researcher (Apache-2.0)
- Agent Search (MIT)
- FirstSignal: ideas only — no licence; no source copied

Full dependency SPDX reuse audit remains open under REM-P1-06.
