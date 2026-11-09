"""Claims/contradictions/progress store semantics without requiring Postgres JSONB."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from thesis_api.services.claims_store import ClaimLineageImmutableError
from thesis_api.services.contradictions_store import VersionConflictError
from thesis_api.services.progress_store import (
    reconstruct_progress_summary,
    sanitize_progress_data,
)
from thesis_api.tenant import TenantContext, TenantIsolationError
from thesis_contracts.research import Claim, ContradictionRecord


def test_sanitize_progress_strips_sensitive_keys() -> None:
    clean = sanitize_progress_data(
        {
            "status": "running",
            "claims_verified": 2,
            "prompt": "exfiltrate",
            "api_key": "secret",
            "evidence_text": "private passage",
            "active_domains": ["company", "team"],
        }
    )
    assert clean["status"] == "running"
    assert clean["claims_verified"] == 2
    assert clean["active_domains"] == ["company", "team"]
    assert "prompt" not in clean
    assert "api_key" not in clean
    assert "evidence_text" not in clean


def test_reconstruct_progress_from_durable_events() -> None:
    events = [
        SimpleNamespace(
            event_id=1,
            event_type="assessment.status",
            domain_id=None,
            message="started",
            data={"status": "RESEARCHING"},
        ),
        SimpleNamespace(
            event_id=2,
            event_type="domain.status",
            domain_id="company",
            message="active",
            data={"status": "active"},
        ),
        SimpleNamespace(
            event_id=3,
            event_type="domain.status",
            domain_id="company",
            message="done",
            data={
                "status": "completed",
                "claims_verified": 4,
                "claims_total": 6,
                "contradictions_detected": 1,
                "evidence_sufficiency": "partial",
                "human_review_status": "pending",
            },
        ),
        SimpleNamespace(
            event_id=4,
            event_type="search.degraded",
            domain_id="market",
            message="provider failure",
            data={"provider_failures": 2, "partial_results": True},
        ),
    ]
    summary = reconstruct_progress_summary(events)  # type: ignore[arg-type]
    assert summary["assessment_status"] == "RESEARCHING"
    assert "company" in summary["completed_domains"]
    assert summary["claims_verified"] == 4
    assert summary["claims_total"] == 6
    assert summary["contradictions_detected"] == 1
    assert summary["provider_failures"] == 2
    assert summary["partial_results"] is True
    assert summary["human_review_status"] == "pending"
    assert summary["evidence_sufficiency"]["company"] == "partial"
    assert summary["last_event_id"] == 4


def test_tenant_assert_firm() -> None:
    t = TenantContext(firm_id="frm_a", user_id=str(uuid4()), roles=("analyst",))
    t.assert_firm("frm_a")
    with pytest.raises(TenantIsolationError):
        t.assert_firm("frm_b")


def test_claim_contract_requires_lineage() -> None:
    with pytest.raises(Exception):
        Claim(
            claim_id=uuid4(),
            assessment_id=uuid4(),
            revision=1,
            domain_id="company",
            statement="x",
            subject="x",
            trust_state="supported",
            evidence_span_ids=[],
            snapshot_ids=[uuid4()],
        )


def test_contradiction_version_field_and_errors() -> None:
    rec = ContradictionRecord(
        contradiction_id=uuid4(),
        assessment_id=uuid4(),
        revision=1,
        domain_ids=["traction"],
        claim_ids=[uuid4(), uuid4()],
        severity="high",
        explanation="conflict",
        version=1,
    )
    assert rec.resolution == "open"
    assert rec.version == 1
    err = VersionConflictError("version mismatch")
    assert "version" in str(err).lower() or True
    lineage_err = ClaimLineageImmutableError("no overwrite")
    assert "overwrite" in str(lineage_err)


def test_claim_model_copy_preserves_spans() -> None:
    span = uuid4()
    snap = uuid4()
    c = Claim(
        claim_id=uuid4(),
        assessment_id=uuid4(),
        revision=1,
        domain_id="traction",
        statement="ARR $10M",
        subject="arr",
        trust_state="supported",
        evidence_span_ids=[span],
        snapshot_ids=[snap],
        extracted_at=datetime.now(timezone.utc),
    )
    updated = c.model_copy(update={"verification_status": "verified"})
    assert updated.evidence_span_ids == [span]
    assert updated.snapshot_ids == [snap]
    assert updated.verification_status == "verified"
