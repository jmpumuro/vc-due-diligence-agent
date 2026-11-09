"""Twelve diligence domains and level availability."""

from __future__ import annotations

from thesis_contracts.base import DomainId, Level

LEVEL1_DOMAINS: tuple[DomainId, ...] = (
    "company",
    "team",
    "market",
    "product",
    "thesis_fit",
)

LEVEL2_EXTRA: tuple[DomainId, ...] = (
    "competition",
    "traction",
    "capitalization",
    "legal",
    "security",
    "governance",
)

LEVEL3_EXTRA: tuple[DomainId, ...] = ("financials",)

ALL_DOMAINS: tuple[DomainId, ...] = (
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
)


def domains_for_level(level: Level) -> list[DomainId]:
    if level == 1:
        return list(LEVEL1_DOMAINS)
    if level == 2:
        return list(LEVEL1_DOMAINS) + list(LEVEL2_EXTRA)
    return list(ALL_DOMAINS)


def min_corroborated_for_level(level: Level) -> int:
    if level == 1:
        return 1
    if level == 2:
        return 2
    return 2
