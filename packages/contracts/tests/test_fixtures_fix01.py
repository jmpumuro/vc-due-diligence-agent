"""FIX-01: seed fixtures validate against contracts (positive + negative cases)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from thesis_contracts.dd import (
    EVENT_DATA_KEYS,
    AssessmentSummaryView,
    CalculationResult,
    DomainConfigSet,
    DocumentVersion,
    Event,
    FinancialTable,
    Finding,
    InformationRequest,
    ReportVersion,
    RiskItem,
    SubmitReviewRequest,
)

ROOT = Path(__file__).resolve().parents[3]
DD = ROOT / "fixtures" / "dd"


def _load(name: str):
    return json.loads((DD / name).read_text())


def test_assessment_summaries() -> None:
    AssessmentSummaryView.model_validate(_load("assessment_summary.json"))
    AssessmentSummaryView.model_validate(_load("assessment_summary_level1.json"))


def test_documents_and_tables() -> None:
    for row in _load("documents.json"):
        DocumentVersion.model_validate(row)
    FinancialTable.model_validate(_load("financial_table.json"))
    FinancialTable.model_validate(_load("financial_table_v2_validated.json"))


def test_findings_calcs_risks_requests() -> None:
    for row in _load("findings_sample.json"):
        Finding.model_validate(row)
    for row in _load("calculations.json"):
        CalculationResult.model_validate(row)
    for row in _load("risks.json"):
        RiskItem.model_validate(row)
    for row in _load("information_requests.json"):
        InformationRequest.model_validate(row)


def test_report_and_config_and_review() -> None:
    ReportVersion.model_validate(_load("report_version.json"))
    DomainConfigSet.model_validate(_load("domain_config.json"))
    SubmitReviewRequest.model_validate(_load("submit_review_request_information.json"))


def test_events() -> None:
    lines = (DD / "events.ndjson").read_text().strip().splitlines()
    assert len(lines) == 14
    for line in lines:
        ev = Event.model_validate(json.loads(line))
        assert set(ev.data.keys()) <= EVENT_DATA_KEYS.get(ev.type, set(ev.data.keys()))


def test_negative_finding_without_basis() -> None:
    good = _load("findings_sample.json")[0]
    bad = {**good, "claim_ids": [], "calculation_id": None, "based_on_finding_ids": [], "kind": "inference"}
    with pytest.raises(ValidationError):
        Finding.model_validate(bad)


def test_negative_validated_table_with_failed_check() -> None:
    table = _load("financial_table_v2_validated.json")
    table = {**table, "checks": [{**c, "passed": False} if c["check"] == "foots" else c for c in table["checks"]]}
    with pytest.raises(ValidationError):
        FinancialTable.model_validate(table)


def test_negative_coverage_not_twelve() -> None:
    summary = _load("assessment_summary.json")
    measures = summary["measures"]
    measures = {
        **measures,
        "evidence_coverage": {**measures["evidence_coverage"], "domains_not_run": 99},
    }
    summary = {**summary, "measures": measures}
    with pytest.raises(ValidationError):
        AssessmentSummaryView.model_validate(summary)
