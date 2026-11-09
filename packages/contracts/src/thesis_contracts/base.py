"""Shared base model and vocabularies."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

Level = Literal[1, 2, 3]
DomainId = Literal[
    "company",
    "team",
    "market",
    "competition",
    "product",
    "traction",
    "financials",
    "capitalization",
    "legal",
    "security",
    "governance",
    "thesis_fit",
]
Recommendation = Literal["advance", "hold", "pass", "inconclusive"]
FindingKind = Literal[
    "verified_fact",
    "source_supported",
    "derived_calculation",
    "inference",
    "contradictory",
    "missing",
    "unresolved_risk",
]
GateResult = Literal[
    "sufficient",
    "partial",
    "insufficient",
    "not_applicable",
    "unavailable_at_level",
]
Stage = Literal[
    "planning",
    "ingesting_documents",
    "domains_running",
    "awaiting_validation",
    "follow_up_research",
    "domain_gates",
    "cross_domain_check",
    "evidence_freeze",
    "evaluating",
    "critiquing",
    "report_writing",
    "report_ready",
]
Access = Literal["workspace", "deal_team"]
AgentRole = Literal[
    "discovery",
    "planner",
    "research",
    "verification",
    "evaluation",
    "critic",
    "memo",
    "monitoring",
]

SECTION_KEYS = [
    "executive_summary",
    "company_overview",
    "thesis_alignment",
    "business_model",
    "team",
    "market",
    "competition",
    "product_technology",
    "traction",
    "financial_analysis",
    "capitalization",
    "legal_regulatory",
    "security_operational",
    "red_flags",
    "contradictions",
    "coverage_confidence",
    "missing_information",
    "scenarios",
    "next_actions",
    "ic_considerations",
    "evidence_appendix",
]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
