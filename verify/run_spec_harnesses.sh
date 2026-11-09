#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Re-runs the three specification harnesses shipped in this package (FIX-01, HAR-D4, SITE-D6).
# They test the spec artefacts (seed data, OCR thresholds, D6 fixture site), NOT the product.
# Requirements: python3 >= 3.11, tesseract 5.x on PATH, and
#   pip install pydantic pytest selectolax pypdf pdfplumber pypdfium2 pytesseract rapidfuzz reportlab pillow
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
echo "== FIX-01 seed data vs contracts =="; (cd "$HERE/fixtures" && python3 build_fixtures.py | tail -3)
echo "== HAR-D4 OCR harness ==";           (cd "$HERE/fixtures/d4-ocr" && python3 -m pytest -q test_d4.py)
echo "== SITE-D6 fixture site ==";         (cd "$HERE/fixtures/d6-site" && python3 -m pytest -q test_site.py)
echo "== package integrity ==";            (cd "$HERE" && sha256sum -c --quiet MANIFEST.sha256 && echo "MANIFEST OK")
