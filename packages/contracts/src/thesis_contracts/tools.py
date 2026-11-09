"""Tool envelope, names, and error taxonomy."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from thesis_contracts.base import AgentRole, Strict
from thesis_contracts.provenance import ArtifactRef

ToolName = Literal[
    "web_search",
    "fetch_url",
    "render_page",
    "github_read",
    "filings_read",
    "rss_read",
    "evidence_lookup",
    "diff_snapshots",
    "document_lookup",
    "table_extract",
    "ddcalc",
    "checklist_review",
    "sanctions_check",
    "dns_tls_check",
    "github_profile",
]

ToolErrorCode = Literal[
    "MISSING_CREDENTIALS",
    "SEARCH_UNAVAILABLE",
    "SEARCH_DEGRADED",
    "SOURCE_BLOCKED",
    "SOURCE_NOT_FOUND",
    "RATE_LIMITED",
    "TIMEOUT",
    "INVALID_RESPONSE",
    "PARSER_FAILED",
    "BROWSER_FAILED",
    "QUOTA_EXCEEDED",
    "POLICY_DENIED",
    "PARTIAL_RESULTS",
    "CIRCUIT_OPEN",
    "UNSUPPORTED_FORMAT",
    "MIME_MISMATCH",
    "MALWARE_DETECTED",
    "SCANNER_UNAVAILABLE",
    "PARSE_FAILED",
    "ENCRYPTED_DOCUMENT",
    "LIMIT_EXCEEDED",
    "VALIDATION_REQUIRED",
    "NOT_COMPUTABLE",
    "EXTERNAL_AI_NOT_AUTHORIZED",
    "PRIVATE_DATA_EGRESS_BLOCKED",
]

# role → allowed tools (from contracts doc + DD additions)
TOOL_PERMISSIONS: dict[AgentRole, frozenset[ToolName]] = {
    "discovery": frozenset({"web_search", "fetch_url", "rss_read"}),
    "planner": frozenset(),
    "research": frozenset(
        {
            "web_search",
            "fetch_url",
            "render_page",
            "github_read",
            "filings_read",
            "rss_read",
            "evidence_lookup",
            "document_lookup",
            "table_extract",
            "github_profile",
            "dns_tls_check",
        }
    ),
    "verification": frozenset(
        {
            "evidence_lookup",
            "document_lookup",
            "checklist_review",
            "sanctions_check",
            "ddcalc",
        }
    ),
    "evaluation": frozenset({"evidence_lookup", "ddcalc"}),
    "critic": frozenset({"evidence_lookup"}),
    "memo": frozenset({"evidence_lookup"}),
    "monitoring": frozenset(
        {
            "fetch_url",
            "rss_read",
            "github_read",
            "filings_read",
            "diff_snapshots",
            "evidence_lookup",
            "sanctions_check",
        }
    ),
}


class ToolUsage(Strict):
    requests: int = 0
    bytes: int = 0
    billable_units: Decimal = Decimal("0")
    cost_usd: Decimal = Decimal("0")
    cost_certainty: Literal["actual", "estimated", "unknown"] = "unknown"


class ToolRequest(Strict):
    schema_version: Literal["1.0"] = "1.0"
    operation_id: UUID
    firm_id: UUID
    assessment_id: UUID | None = None
    role: AgentRole
    tool_name: ToolName
    args: dict[str, Any]
    budget_ref: UUID | None = None
    deadline_at: datetime
    data_classification: Literal["public", "tenant_private"]


class ToolResult(Strict):
    schema_version: Literal["1.0"] = "1.0"
    operation_id: UUID
    status: Literal["succeeded", "partial", "unavailable", "blocked", "failed"]
    data_ref: ArtifactRef | None = None
    provenance_refs: list[UUID] = []
    provider: str
    latency_ms: int = Field(ge=0)
    usage: ToolUsage
    error_code: ToolErrorCode | None = None
    retryable: bool = False
    diagnostics: dict[str, str] = {}


def tool_allowed(role: AgentRole, tool: ToolName) -> bool:
    return tool in TOOL_PERMISSIONS.get(role, frozenset())
