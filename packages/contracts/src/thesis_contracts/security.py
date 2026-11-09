"""D1–D4 security and data-handling contracts (subset used by Stage 1)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from thesis_contracts.base import Strict

PrivateDataCategory = Literal[
    "document_text",
    "document_tables",
    "financial_figures",
    "deal_notes",
    "identity_pii",
]
AIPurpose = Literal[
    "classify_document",
    "extract_claims",
    "summarize_section",
    "score_rubric",
    "critique",
    "draft_report",
    "entity_resolve",
]


class ModelInputSegment(Strict):
    text: str
    scope: Literal["public", "private"]
    category: PrivateDataCategory | None = None
    document_id: UUID | None = None
    document_version: int | None = None

    @model_validator(mode="after")
    def _private_category(self) -> ModelInputSegment:
        if self.scope == "private" and self.category is None:
            raise ValueError("private segments require category")
        return self


class ModelRequestEnvelope(Strict):
    workspace_id: UUID
    assessment_id: UUID | None = None
    revision: int | None = None
    purpose: AIPurpose
    segments: list[ModelInputSegment]
    operation_id: UUID
    public_only_variant_allowed: bool = False


class PolicyDecision(Strict):
    allowed: bool
    route: Literal["external", "local", "denied"]
    policy_version: int
    reason: str | None = None


class ExternalTransmission(Strict):
    transmission_id: UUID
    workspace_id: UUID
    assessment_id: UUID | None = None
    revision: int | None = None
    policy_version: int
    provider: Literal["openai"]
    model: str
    purpose: AIPurpose
    categories: list[PrivateDataCategory]
    segment_count: int
    char_count: int
    payload_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    operation_id: UUID
    at: datetime


class OcrPageResult(Strict):
    page_number: int = Field(ge=1)
    method: Literal["native_text", "ocr", "ocr_skipped_limit", "ocr_failed"]
    reason: Literal[
        "native_ok",
        "native_chars_low",
        "garbled_text_layer",
        "image_dominated",
    ]
    char_count: int = Field(ge=0)
    ocr_confidence: Decimal | None = None
    engine: str | None = None
