"""Persistent company/founder identity resolution with ambiguity safeguards.

Adapted from FirstSignal identity ideas (no licence on that repo — clean-room).
Names alone never merge companies; ambiguous matches require human review.
"""

from __future__ import annotations

import re
from decimal import Decimal
from uuid import uuid4

from thesis_contracts.research import (
    IdentityResolution,
    IdentitySignal,
    ResolvedIdentityCandidate,
)

_WS = re.compile(r"\s+")
_CORP = re.compile(
    r"\b(inc|incorporated|llc|ltd|limited|gmbh|ag|corp|corporation|co|company|plc|sa|bv)\b\.?",
    re.I,
)


def normalize_name(name: str) -> str:
    s = _WS.sub(" ", name.strip().lower())
    s = _CORP.sub("", s)
    return _WS.sub(" ", s).strip(" ,.-")


def normalize_domain(domain: str | None) -> str | None:
    if not domain:
        return None
    d = domain.strip().lower()
    d = re.sub(r"^https?://", "", d)
    d = d.split("/")[0]
    d = d.removeprefix("www.")
    return d or None


def _name_similarity(a: str, b: str) -> Decimal:
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return Decimal("0")
    if na == nb:
        return Decimal("1")
    # Token Jaccard — deliberately conservative (no fuzzy merge on thin overlap).
    ta, tb = set(na.split()), set(nb.split())
    if not ta or not tb:
        return Decimal("0")
    inter = len(ta & tb)
    union = len(ta | tb)
    return Decimal(inter) / Decimal(union)


def resolve_identity(
    *,
    query_name: str,
    query_domain: str | None,
    known: list[ResolvedIdentityCandidate],
    create_if_missing: bool = True,
    auto_match_threshold: Decimal = Decimal("0.92"),
    ambiguous_band: Decimal = Decimal("0.55"),
) -> IdentityResolution:
    """Match against known candidates; never auto-merge on name-only weak signals."""
    domain = normalize_domain(query_domain)
    scored: list[tuple[Decimal, ResolvedIdentityCandidate, list[IdentitySignal]]] = []

    for cand in known:
        signals: list[IdentitySignal] = []
        conf = Decimal("0")
        cand_domain = normalize_domain(cand.primary_domain)
        if domain and cand_domain and domain == cand_domain:
            signals.append(
                IdentitySignal(
                    kind="exact_domain", value=domain, weight=Decimal("0.95"), source="domain"
                )
            )
            conf = max(conf, Decimal("0.95"))
        sim = _name_similarity(query_name, cand.canonical_name)
        if sim >= Decimal("1"):
            signals.append(
                IdentitySignal(
                    kind="exact_name",
                    value=normalize_name(query_name),
                    weight=Decimal("0.7"),
                    source="name",
                )
            )
            conf = max(conf, Decimal("0.7") if not domain else Decimal("0.85"))
        elif sim >= ambiguous_band:
            signals.append(
                IdentitySignal(
                    kind="fuzzy_name",
                    value=f"{normalize_name(query_name)}~{normalize_name(cand.canonical_name)}",
                    weight=sim,
                    source="name",
                )
            )
            conf = max(conf, sim * Decimal("0.6"))  # name-only fuzzy capped
        if not signals:
            continue
        # Domain mismatch with same name → force ambiguity (similarly named entities).
        ambiguous = bool(
            domain and cand_domain and domain != cand_domain and sim >= Decimal("0.85")
        )
        if ambiguous:
            conf = min(conf, Decimal("0.5"))
        updated = ResolvedIdentityCandidate(
            company_id=cand.company_id,
            canonical_name=cand.canonical_name,
            primary_domain=cand.primary_domain,
            founders=list(cand.founders),
            signals=signals,
            confidence=conf,
            ambiguous=ambiguous or (conf < auto_match_threshold and conf >= ambiguous_band),
        )
        scored.append((conf, updated, signals))

    scored.sort(key=lambda x: x[0], reverse=True)
    candidates = [c for _, c, _ in scored]

    if not candidates:
        if not create_if_missing:
            return IdentityResolution(
                query_name=query_name,
                query_domain=domain,
                outcome="rejected",
                reason="no_candidates",
            )
        created = ResolvedIdentityCandidate(
            company_id=uuid4(),
            canonical_name=query_name.strip(),
            primary_domain=domain,
            confidence=Decimal("1"),
            signals=[
                IdentitySignal(
                    kind="exact_name",
                    value=normalize_name(query_name),
                    weight=Decimal("1"),
                    source="new",
                )
            ],
        )
        return IdentityResolution(
            query_name=query_name,
            query_domain=domain,
            outcome="created",
            selected=created,
            candidates=[created],
        )

    top_conf, top, _ = scored[0]
    # Two close candidates → human review.
    if len(scored) > 1 and (top_conf - scored[1][0]) < Decimal("0.15") and scored[1][0] >= ambiguous_band:
        return IdentityResolution(
            query_name=query_name,
            query_domain=domain,
            outcome="ambiguous",
            candidates=candidates,
            review_required=True,
            reason="competing_candidates",
        )
    if top.ambiguous or top_conf < auto_match_threshold:
        return IdentityResolution(
            query_name=query_name,
            query_domain=domain,
            outcome="ambiguous",
            candidates=candidates,
            review_required=True,
            reason="below_threshold_or_domain_conflict",
        )
    return IdentityResolution(
        query_name=query_name,
        query_domain=domain,
        outcome="matched",
        selected=top,
        candidates=candidates,
    )
