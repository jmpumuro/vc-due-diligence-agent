# ADR-015: PDF library and licence policy

- Status: Accepted
- Date: 2026-11-07

## Decision

Project licence is Apache-2.0 (D5). PDF: pypdf (BSD-3-Clause) primary; pdfplumber for tables; Tesseract OCR via D4 native-first path. At pin time, run the licence gate; report conflicts rather than silently changing the project licence.

## Consequences

AGPL services (SearXNG) and GPL services (ClamAV) run as unmodified separate containers (aggregation). Linked Python deps must pass D5.
