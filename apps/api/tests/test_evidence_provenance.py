"""Stage 4 provenance: snapshot/span hashes, claim lineage, syndication≠independence."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from thesis_api.services.evidence_lineage import check_claim_lineage
from thesis_api.services.evidence_store import sha256_hex
from thesis_api.services.screening_research import (
    claim_from_evidence,
    corroborate_public_docs,
)
from thesis_contracts.provenance import EvidenceSpan
from thesis_contracts.research import Claim


def test_sha256_hex_stable_for_bytes_and_str() -> None:
    body = b"Example Domain"
    assert sha256_hex(body) == sha256_hex("Example Domain")
    assert len(sha256_hex(body)) == 64


def test_claim_from_evidence_requires_real_lineage_ids() -> None:
    snap = str(uuid4())
    span = str(uuid4())
    claim = claim_from_evidence(
        firm_id="frm_demo",
        assessment_id=uuid4(),
        revision=1,
        domain_id="company",
        statement="Public identity page retrieved",
        subject="company",
        snapshot_id=snap,
        span_id=span,
        source_url="https://example.com/",
        confidence=Decimal("0.62"),
    )
    assert claim.snapshot_ids == [UUID(snap)]
    assert claim.evidence_span_ids == [UUID(span)]
    assert claim.source_urls == ["https://example.com/"]
    assert claim.trust_state == "supported"


def test_lineage_check_ok_when_span_matches_snapshot() -> None:
    snap = uuid4()
    span_id = uuid4()
    claim = Claim(
        claim_id=uuid4(),
        assessment_id=uuid4(),
        revision=1,
        domain_id="company",
        statement="HQ signal",
        subject="company",
        trust_state="supported",
        evidence_span_ids=[span_id],
        snapshot_ids=[snap],
    )
    spans = {
        span_id: EvidenceSpan(
            span_id=span_id,
            snapshot_id=snap,
            start=0,
            end=8,
            text="HQ signal",
            text_sha256=sha256_hex("HQ signal"),
        )
    }
    check = check_claim_lineage(claim, spans, known_snapshot_ids={snap})
    assert check.ok is True
    assert check.missing == []


def test_syndicated_mirror_does_not_inflate_independence() -> None:
    from thesis_api.services.corroboration import SourceDocument

    text = "Example Domain This domain is for use in documentation examples."
    corr = corroborate_public_docs(
        claim_key="demo:company",
        documents=[
            SourceDocument(
                url="https://example.com/",
                content_text=text,
                search_rank=1,
                is_primary=True,
            ),
            SourceDocument(
                url="https://example.com/mirror",
                content_text=text,
                search_rank=2,
            ),
        ],
        query_terms=["Example", "Domain", "company"],
    )
    assert corr["independent_count"] == 1
    assert corr["syndicated_groups"] or corr["independent_count"] < 2
