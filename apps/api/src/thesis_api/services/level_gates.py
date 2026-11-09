# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""Level 2/3 screening readiness — public research vs private AI (D1)."""

from __future__ import annotations

from thesis_api.settings import settings


def level3_docs_pipeline_ready() -> bool:
    """True when D4 product OCR path is operator-verified.

    ClamAV + worker-docs may already be healthy; this flag is flipped only after
    `scripts/smoke_d4_product.py` (or CI equivalent) is green. Private document
    *AI* stays fail-closed separately via PolicyEnforcedProvider (D1).
    """
    return bool(settings.ocr_product_verified)


def level3_screening_allowed() -> bool:
    """Public+financials Level 3 CompanyScreeningWorkflow may start."""
    return level3_docs_pipeline_ready()


def level3_private_ai_allowed() -> bool:
    """Private-document model calls — always false until a verified local route."""
    return False
