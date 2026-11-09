"""Pydantic v2 transcription of the due diligence contracts (plan doc: Master plan + Agent & tool contracts).

Used only to validate the fixture set in fixtures/dd/. Types marked SUPPORTING were not spelled out in the
contracts before 2026-11-07 and are defined here; the contracts tab now lists them under "Supporting types".
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# ---------- shared vocabularies ----------
Level = Literal[1, 2, 3]
DomainId = Literal["company", "team", "market", "competition", "product", "traction",
                   "financials", "capitalization", "legal", "security", "governance", "thesis_fit"]
Recommendation = Literal["advance", "hold", "pass", "inconclusive"]
FindingKind = Literal["verified_fact", "source_supported", "derived_calculation", "inference",
                      "contradictory", "missing", "unresolved_risk"]
GateResult = Literal["sufficient", "partial", "insufficient", "not_applicable", "unavailable_at_level"]
Stage = Literal["planning", "ingesting_documents", "domains_running", "awaiting_validation", "follow_up_research",
                "domain_gates", "cross_domain_check", "evidence_freeze", "evaluating", "critiquing",
                "report_writing", "report_ready"]
AssessmentState = Literal["CREATED", "PLANNING", "RESEARCHING", "VALIDATING", "EVALUATING", "CRITIQUING",
                          "MEMO_READY", "AWAITING_REVIEW", "INFORMATION_REQUESTED", "DELIVERING", "COMPLETED",
                          "REJECTED", "BLOCKED_CONFIGURATION", "BUDGET_EXHAUSTED", "CANCELLED", "FAILED"]
Access = Literal["workspace", "deal_team"]


# ---------- SUPPORTING types ----------
class CompanyAlias(Strict):
    value: str
    kind: Literal["name", "domain"]
    source: str
    confidence: Decimal


class CompanyRef(Strict):
    company_id: UUID
    canonical_name: str
    primary_domain: str | None
    aliases: list[CompanyAlias] = []


class PeriodRange(Strict):  # SUPPORTING
    start: date
    end: date
    granularity: Literal["month", "quarter", "year", "point"]

    @model_validator(mode="after")
    def _order(self):
        if self.end < self.start:
            raise ValueError("period end before start")
        return self


class SheetLocator(Strict):  # SUPPORTING
    kind: Literal["sheet"] = "sheet"
    sheet: str
    cell: str                      # A1 notation


class PageLocator(Strict):  # SUPPORTING
    kind: Literal["page"] = "page"
    page: int
    bbox: tuple[Decimal, Decimal, Decimal, Decimal] | None = None


class SlideLocator(Strict):  # SUPPORTING
    kind: Literal["slide"] = "slide"
    slide: int


class ParagraphLocator(Strict):  # SUPPORTING
    kind: Literal["paragraph"] = "paragraph"
    paragraph: int


Locator = SheetLocator | PageLocator | SlideLocator | ParagraphLocator


class InputRef(Strict):  # SUPPORTING: one traced input to a calculation
    name: str                      # formula variable, e.g. "cash_end"
    value: Decimal
    unit: str
    period: PeriodRange
    financial_table_id: UUID | None = None
    table_version: int | None = None
    document_id: UUID | None = None
    document_version: int | None = None
    locator: Locator | None = None
    claim_id: UUID | None = None

    @model_validator(mode="after")
    def _traceable(self):
        if not (self.financial_table_id or self.document_id or self.claim_id):
            raise ValueError("input must trace to a table, document or claim")
        return self


class ScorecardRow(Strict):  # SUPPORTING
    criterion_id: str
    score: int | None = Field(default=None, ge=1, le=5)
    weight: Decimal
    facts_count: int
    evidence_strength: Literal["strong", "good", "mixed", "weak"]
    rationale: str
    revised_after_critique: bool
    finding_ids: list[UUID]


# ---------- measures & summary ----------
class SourceReliability(Strict):
    label: Literal["strong", "good", "fair", "weak"]
    independent_share: Decimal
    company_only_share: Decimal


class ClaimConfidence(Strict):
    label: Literal["high", "medium", "low"]
    verified: int
    source_supported: int
    inference: int


class EvidenceCoverage(Strict):
    domains_sufficient: int
    domains_partial: int
    domains_insufficient: int
    domains_not_run: int

    @model_validator(mode="after")
    def _twelve(self):
        if self.domains_sufficient + self.domains_partial + self.domains_insufficient + self.domains_not_run != 12:
            raise ValueError("coverage must account for 12 domains")
        return self


class Attractiveness(Strict):
    score: Decimal | None
    range: tuple[Decimal, Decimal] | None
    advance_threshold: Decimal


class Measures(Strict):
    source_reliability: SourceReliability
    claim_confidence: ClaimConfidence
    evidence_coverage: EvidenceCoverage
    attractiveness: Attractiveness


class DomainStatusSummary(Strict):
    domain_id: DomainId
    status: Literal["pending", "running", "complete", "partial", "failed", "skipped"]
    gate_result: GateResult
    reason: str | None
    sources_found: int
    sources_required: int
    findings: int
    contradictions: int
    risks: int
    requests: int
    can_retry: bool


class Progress(Strict):
    stage: Stage
    domains_complete: int
    domains_total: int
    documents_ready: int | None = None
    documents_total: int | None = None


class AssessmentSummaryView(Strict):
    assessment_id: UUID
    company: CompanyRef
    revision: int
    level: Level
    state: AssessmentState
    stage: Stage | None
    status_copy_key: str
    recommendation: Recommendation | None
    conditions: list[str] = []
    headline: str | None
    measures: Measures | None
    domains: list[DomainStatusSummary]
    finding_counts: dict[FindingKind, int]
    open_risks: int
    open_requests: int
    advance_threshold: Decimal
    thesis_fit: Literal["strong", "moderate", "weak", "out_of_mandate"] | None
    scorecard: list[ScorecardRow]
    progress: Progress | None
    can_decide: bool
    report_version_id: UUID | None

    @model_validator(mode="after")
    def _rules(self):
        if len(self.domains) != 12 or len({d.domain_id for d in self.domains}) != 12:
            raise ValueError("summary must list each of the 12 domains once")
        if self.conditions and self.recommendation != "advance":
            raise ValueError("conditions only with advance")
        if self.measures:
            cov = self.measures.evidence_coverage
            suff = sum(d.gate_result == "sufficient" for d in self.domains)
            if cov.domains_sufficient != suff:
                raise ValueError("coverage.domains_sufficient disagrees with domain rows")
        return self


# ---------- findings, calculations ----------
class Finding(Strict):
    finding_id: UUID
    assessment_id: UUID
    revision: int
    domain_id: DomainId
    kind: FindingKind
    statement: str
    claim_ids: list[UUID] = []
    calculation_id: UUID | None = None
    based_on_finding_ids: list[UUID] = []
    claim_confidence: Literal["high", "medium", "low"]
    materiality: Literal["critical", "high", "medium", "low"]
    evidence_scope: Literal["public", "private", "mixed"]
    access: Access

    @model_validator(mode="after")
    def _basis(self):
        if not (self.claim_ids or self.calculation_id or self.based_on_finding_ids or self.kind == "missing"):
            raise ValueError("finding needs a claim, calculation or basis (except missing)")
        if self.evidence_scope != "public" and self.access != "deal_team":
            raise ValueError("private evidence must be deal_team access")
        return self


class CalculationResult(Strict):
    calculation_id: UUID
    metric: str
    formula_version: str
    status: Literal["computed", "not_computable", "flagged"]
    value: Decimal | None
    unit: str
    currency: str | None
    period: PeriodRange
    inputs: list[InputRef]
    assumptions: list[str]
    missing_inputs: list[str] = []
    validation_issues: list[str] = []

    @model_validator(mode="after")
    def _status(self):
        if self.status == "not_computable" and (self.value is not None or not self.missing_inputs):
            raise ValueError("not_computable needs missing_inputs and no value")
        if self.status != "not_computable" and (self.value is None or not self.inputs):
            raise ValueError("computed/flagged need a value and traced inputs")
        if self.status == "flagged" and not self.validation_issues:
            raise ValueError("flagged needs validation_issues")
        return self


# ---------- documents & tables ----------
class DocumentVersion(Strict):
    document_id: UUID
    version: int
    assessment_id: UUID
    filename: str
    declared_mime: str
    detected_mime: str | None
    size_bytes: int
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["uploaded", "scanning", "rejected", "quarantined", "parsing", "classified",
                    "needs_validation", "ready", "failed"]
    reject_reason: str | None
    classification: Literal["pitch_deck", "financials", "cap_table", "customer_revenue", "contract", "policy",
                            "board_material", "other"] | None
    classification_source: Literal["model", "user"] | None
    parser: str | None
    page_count: int | None
    injection_flags: int = 0
    uploaded_by: UUID
    object_key: str
    key_id: str

    @model_validator(mode="after")
    def _reject(self):
        if self.status in ("rejected", "quarantined") and (not self.reject_reason or self.parser):
            raise ValueError("rejected/quarantined need a reason and must not have been parsed")
        return self


class FinancialCell(Strict):  # SUPPORTING
    period: PeriodRange
    value: Decimal | None
    raw: str
    locator: SheetLocator | PageLocator
    confidence: Decimal = Field(ge=0, le=1)


class FinancialRow(Strict):  # SUPPORTING
    line: str
    is_total: bool = False
    total_of: list[str] = []
    total_rule: Literal["sum", "rollforward"] | None = None   # rollforward: total[i] = total[i-1] + sum(parts[i])
    cells: list[FinancialCell]


class TableCheck(Strict):  # SUPPORTING
    check: Literal["foots", "contiguous_periods", "single_currency", "sign_convention", "low_confidence_cells"]
    passed: bool
    detail: str | None = None


class Correction(Strict):  # SUPPORTING
    correction_id: UUID
    author: UUID
    line: str
    period_start: date
    old_value: Decimal | None
    new_value: Decimal
    reason: str = Field(min_length=3)
    at: datetime


class FinancialTable(Strict):
    financial_table_id: UUID
    version: int
    document_id: UUID
    statement: Literal["income", "balance", "cash_flow", "kpi", "cap_table", "customer_revenue", "pipeline"]
    currency: str | None
    periods: list[PeriodRange]
    rows: list[FinancialRow]
    checks: list[TableCheck]
    status: Literal["draft", "needs_validation", "validated"]
    validated_by: UUID | None
    corrections: list[Correction] = []

    @model_validator(mode="after")
    def _consistency(self):
        failed = [c for c in self.checks if not c.passed]
        if self.status == "validated" and (failed or not self.validated_by):
            raise ValueError("validated tables need all checks passing and a validator")
        if self.status == "needs_validation" and not failed:
            raise ValueError("needs_validation without a failed check")
        # recompute 'foots' so a fixture (or a parser) cannot claim a table adds up when it does not
        by_line = {r.line: r for r in self.rows}
        foots = True
        for r in self.rows:
            if not r.is_total:
                continue
            for i, cell in enumerate(r.cells):
                parts = [by_line[n].cells[i].value for n in r.total_of]
                if cell.value is None or any(p is None for p in parts):
                    continue
                if r.total_rule == "sum":
                    expected = sum(parts)
                elif i == 0:
                    continue
                else:
                    prev = r.cells[i - 1].value
                    if prev is None:
                        continue
                    expected = prev + sum(parts)
                if expected != cell.value:
                    foots = False
        declared = next((c.passed for c in self.checks if c.check == "foots"), None)
        if declared is not None and declared != foots:
            raise ValueError(f"'foots' check declared {declared} but recomputation gives {foots}")
        return self


# ---------- risks, requests, scenarios ----------
class RiskItem(Strict):
    risk_id: UUID
    assessment_id: UUID
    domain_ids: list[DomainId]
    title: str
    description: str
    severity: Literal["critical", "high", "medium", "low"]
    likelihood: Literal["likely", "possible", "unlikely", "unknown"]
    finding_ids: list[UUID] = Field(min_length=1)
    mitigation_question: str | None
    status: Literal["open", "accepted", "mitigated", "closed"]
    owner_user_id: UUID | None
    access: Access


class InformationRequest(Strict):
    request_id: UUID
    assessment_id: UUID
    domain_id: DomainId
    requested_item: str
    reason: str
    blocking: bool
    status: Literal["draft", "sent", "received", "waived", "closed"]
    linked_document_ids: list[UUID] = []
    created_by: Literal["system", "user"]


# ---------- report ----------
SECTION_KEYS = ["executive_summary", "company_overview", "thesis_alignment", "business_model", "team",
                "market", "competition", "product_technology", "traction", "financial_analysis",
                "capitalization", "legal_regulatory", "security_operational", "red_flags", "contradictions",
                "coverage_confidence", "missing_information", "scenarios", "next_actions",
                "ic_considerations", "evidence_appendix"]


class ReportSection(Strict):
    number: int = Field(ge=1, le=21)
    key: str
    status: Literal["supported", "incomplete", "not_applicable", "unavailable_at_level"]
    status_reason: str | None
    body_md: str
    finding_ids: list[UUID]
    access: Access


class ReportVersion(Strict):
    report_version_id: UUID
    assessment_id: UUID
    revision: int
    level: Level
    schema_version: Literal["ddreport@1"] = "ddreport@1"
    evidence_snapshot_set_id: UUID
    recommendation: Recommendation
    conditions: list[str] = []
    measures: Measures
    sections: list[ReportSection]
    disclaimers: list[str]
    created_at: datetime
    approved_by: UUID | None

    @model_validator(mode="after")
    def _sections(self):
        if [s.number for s in self.sections] != list(range(1, 22)):
            raise ValueError("exactly 21 sections in order")
        if [s.key for s in self.sections] != SECTION_KEYS:
            raise ValueError("section keys out of order")
        for s in self.sections:
            if s.status != "supported" and not s.status_reason:
                raise ValueError(f"section {s.number} needs status_reason")
            if s.status == "supported" and not s.finding_ids and s.number not in (19, 20):
                raise ValueError(f"supported section {s.number} must cite findings")
        if self.conditions and self.recommendation != "advance":
            raise ValueError("conditions only with advance")
        return self


# ---------- review ----------
class ReviewTarget(Strict):
    assessment_id: UUID
    assessment_revision: int
    evidence_snapshot_id: UUID
    evaluation_id: UUID
    memo_version_id: UUID
    review_policy_version: str


class SubmitReviewRequest(Strict):
    target: ReviewTarget
    decision: Literal["approve", "reject", "request_research", "request_information"]
    comment: str | None = None
    requested_items: list[str] = []
    idempotency_key: str

    @model_validator(mode="after")
    def _items(self):
        if self.decision == "request_information" and not self.requested_items:
            raise ValueError("request_information needs requested_items")
        return self


# ---------- configuration ----------
class OverrideCondition(Strict):  # SUPPORTING
    stage: list[str] | None = None
    industry: list[str] | None = None
    geography: list[str] | None = None
    thesis_tag: list[str] | None = None


class DomainOverride(Strict):
    when: OverrideCondition
    set: dict[str, Any]


class DomainConfig(Strict):
    domain_id: DomainId
    enabled: bool = True
    required_for_recommendation: bool
    levels: list[Level]
    weight: Decimal
    min_sources: dict[str, int]       # keys "1","2","3" (JSON object keys are strings)
    task_budget: dict[str, int]
    overrides: list[DomainOverride] = []


class DomainConfigSet(Strict):  # body of GET/PUT /config/domains
    config_version: int
    domains: list[DomainConfig]

    @model_validator(mode="after")
    def _all(self):
        ids = [d.domain_id for d in self.domains]
        if len(ids) != 12 or len(set(ids)) != 12:
            raise ValueError("all 12 domains, once each")
        tf = next(d for d in self.domains if d.domain_id == "thesis_fit")
        if not tf.enabled:
            raise ValueError("DOMAIN_REQUIRED: thesis_fit cannot be disabled")
        return self


# ---------- events ----------
class Subject(Strict):
    kind: str
    id: str


class Event(Strict):
    id: str
    type: str
    version: Literal[1]
    occurred_at: datetime
    sequence: int
    subject: Subject
    audience: Literal["research", "console"]
    data: dict[str, Any]


EVENT_DATA_KEYS: dict[str, set[str]] = {
    "assessment.progress": {"assessment_id", "revision", "stage", "domains_complete", "domains_total"},
    "domain.status_changed": {"assessment_id", "revision", "domain_id", "status", "gate_result"},
    "document.status_changed": {"document_id", "version", "status", "reason"},
    "financials.validation_required": {"financial_table_id", "version", "issue_count"},
    "financials.validated": {"financial_table_id", "version", "issue_count"},
    "contradiction.detected": {"assessment_id", "contradiction_id", "domain_ids"},
    "risk.updated": {"risk_id", "severity", "status"},
    "information_request.updated": {"request_id", "status"},
    "report.version_created": {"report_version_id", "level", "revision"},
    "assessment.memo_ready": {"assessment_id", "memo_version_id"},
    "assessment.revision_created": {"assessment_id", "revision", "reason"},
    "run.stage_started": {"assessment_id", "state", "stage", "queue", "attempt"},
    "config.version_created": {"version", "changed"},
    "review.decided": {"assessment_id", "decision", "target_digest"},
}
