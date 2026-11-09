"""Value-of-information planning — prioritize unanswered diligence questions.

Inspired by FirstSignal DiligenceAction (ideas only) and GPT-Researcher outline planning.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from thesis_contracts.base import DomainId, GateResult
from thesis_contracts.research import VoIAction


def plan_voi_actions(
    *,
    assessment_id: UUID,
    domain_gates: dict[DomainId, GateResult],
    unanswered_questions: dict[DomainId, list[str]],
    open_contradiction_domains: set[DomainId],
    budget_usd_remaining: Decimal,
) -> list[VoIAction]:
    """Rank follow-ups: contradictions and insufficient gates first."""
    actions: list[VoIAction] = []
    for domain, gate in domain_gates.items():
        impact = Decimal("0.3")
        blocking = False
        if domain in open_contradiction_domains:
            impact = Decimal("0.9")
            blocking = True
        elif gate == "insufficient":
            impact = Decimal("0.8")
            blocking = True
        elif gate == "partial":
            impact = Decimal("0.55")
        questions = unanswered_questions.get(domain, [])
        if not questions and blocking:
            questions = [f"Resolve evidence gaps for domain {domain}"]
        for q in questions:
            cost = Decimal("0.15") if blocking else Decimal("0.08")
            if cost > budget_usd_remaining:
                continue
            actions.append(
                VoIAction(
                    action_id=uuid4(),
                    assessment_id=assessment_id,
                    domain_id=domain,
                    question=q,
                    expected_decision_impact=impact,
                    cost_estimate_usd=cost,
                    rationale=f"gate={gate}; blocking={blocking}",
                    blocking_gate=blocking,
                )
            )
    actions.sort(
        key=lambda a: (a.blocking_gate, a.expected_decision_impact),
        reverse=True,
    )
    # Bound follow-ups (GPT-Researcher-style loop bound).
    return actions[:12]
