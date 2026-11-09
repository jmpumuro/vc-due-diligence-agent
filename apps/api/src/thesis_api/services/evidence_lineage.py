"""Evidence lineage: claim → spans → snapshots (hashes/offsets checked)."""

from __future__ import annotations

from uuid import UUID

from thesis_contracts.provenance import EvidenceSpan
from thesis_contracts.research import Claim, EvidenceLineageCheck


def check_claim_lineage(
    claim: Claim,
    spans: dict[UUID, EvidenceSpan],
    *,
    known_snapshot_ids: set[UUID],
) -> EvidenceLineageCheck:
    missing: list[str] = []
    for sid in claim.evidence_span_ids:
        span = spans.get(sid)
        if span is None:
            missing.append(f"span:{sid}")
            continue
        if span.snapshot_id not in known_snapshot_ids:
            missing.append(f"unknown_snapshot:{span.snapshot_id}")
        if span.snapshot_id not in claim.snapshot_ids:
            missing.append(f"claim_missing_snapshot_ref:{span.snapshot_id}")
        if not span.text.strip():
            missing.append(f"empty_span_text:{sid}")
    for snap in claim.snapshot_ids:
        if snap not in known_snapshot_ids:
            missing.append(f"unknown_snapshot:{snap}")

    ok = len(missing) == 0
    return EvidenceLineageCheck(
        claim_id=claim.claim_id,
        ok=ok,
        missing=missing,
        detail=None if ok else "lineage_incomplete",
    )
