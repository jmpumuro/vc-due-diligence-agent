# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""Numeric / metric claim grounding against cited passage text.

A claim that states dollars, headcount, users, or years must either:
- have those facts appear on the cited evidence text, or
- not be marked trust_state=supported / verification=verified.

This is the contract the research path and value tester share.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import Field

from thesis_contracts.base import Strict

FACT_RE = re.compile(
    r"""
    (?:\$\s?\d[\d,\.]*(?:\s*(?:million|billion|m|b))?)
    |(?:\d[\d,\.]*\s*(?:million|billion)\s+(?:users|customers|employees|people)?)
    |(?:\b(?:19|20)\d{2}\b)
    |(?:\b\d{2,4}\s*(?:\+\s*)?(?:employees|users|customers|therapists)\b)
    """,
    re.I | re.X,
)

GroundingVerdict = Literal[
    "no_numeric_facts",
    "fully_grounded",
    "partially_grounded",
    "ungrounded",
]


class NumericGroundingResult(Strict):
    statement: str
    facts: list[str] = []
    supported_facts: list[str] = []
    missing_facts: list[str] = []
    verdict: GroundingVerdict
    ok_for_supported: bool
    detail: str | None = None


class ClaimGroundingPolicy(Strict):
    """Policy knobs for research / eval (defaults are industry-cautious)."""

    demote_ungrounded_to: Literal["unsupported", "insufficient", "contested"] = "insufficient"
    allow_supported_without_passage: bool = False
    max_ungrounded_facts_for_partial: int = Field(default=0, ge=0)


def extract_numeric_facts(statement: str) -> list[str]:
    return [m.group(0).strip() for m in FACT_RE.finditer(statement or "")]


def _norm(s: str) -> str:
    t = (s or "").lower().replace(",", "")
    t = t.replace("$", " $ ")
    t = re.sub(r"\s+", " ", t).strip()
    t = t.replace(" billion", "b").replace(" million", "m")
    return t


def fact_in_text(fact: str, text: str) -> bool:
    if not fact or not text:
        return False
    raw = text.lower()
    if fact.lower() in raw:
        return True
    return _norm(fact) in _norm(text)


def ground_numeric_statement(statement: str, passage: str | None) -> NumericGroundingResult:
    facts = extract_numeric_facts(statement)
    if not facts:
        return NumericGroundingResult(
            statement=statement,
            facts=[],
            supported_facts=[],
            missing_facts=[],
            verdict="no_numeric_facts",
            ok_for_supported=True,
            detail="no numeric / scale facts to ground",
        )
    page = passage or ""
    supported = [f for f in facts if fact_in_text(f, page)]
    missing = [f for f in facts if f not in supported]
    if not missing:
        verdict: GroundingVerdict = "fully_grounded"
    elif not supported:
        verdict = "ungrounded"
    else:
        verdict = "partially_grounded"
    return NumericGroundingResult(
        statement=statement,
        facts=facts,
        supported_facts=supported,
        missing_facts=missing,
        verdict=verdict,
        ok_for_supported=verdict == "fully_grounded",
        detail=(
            None
            if verdict == "fully_grounded"
            else f"missing on cited passage: {', '.join(missing)}"
        ),
    )


def trust_for_grounding(
    result: NumericGroundingResult,
    *,
    policy: ClaimGroundingPolicy | None = None,
) -> tuple[str, str, str]:
    """Return (trust_state, verification_status, claim_type) after grounding."""
    policy = policy or ClaimGroundingPolicy()
    if result.verdict == "no_numeric_facts":
        return "supported", "extracted", "fact"
    if result.ok_for_supported:
        return "supported", "verified", "metric"
    demote = policy.demote_ungrounded_to
    if demote == "insufficient":
        return "insufficient", "insufficient", "metric"
    if demote == "contested":
        return "contested", "contested", "metric"
    return "unsupported", "insufficient", "metric"
