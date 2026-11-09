"""Evidence provenance — snapshots, spans, artifact refs."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, HttpUrl, model_validator

from thesis_contracts.base import Strict


class ArtifactRef(Strict):
    artifact_id: UUID
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_type: str
    byte_size: int = Field(ge=0)
    storage_key: str


class SourceSnapshotMeta(Strict):
    snapshot_id: UUID
    canonical_url: HttpUrl
    retrieved_at: datetime
    http_status: int
    content_type: str
    normalized_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_artifact: ArtifactRef
    normalized_artifact: ArtifactRef
    classification: Literal["public"] = "public"


class EvidenceSpan(Strict):
    span_id: UUID
    snapshot_id: UUID
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    text: str
    text_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _order(self) -> EvidenceSpan:
        if self.end < self.start:
            raise ValueError("span end before start")
        return self
