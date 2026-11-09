# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from thesis_api.services.domains import domains_for_level
from thesis_api.services.screening import plan_domains


def test_level1_five_public_domains() -> None:
    d = plan_domains(1)
    assert d == ["company", "team", "market", "product", "thesis_fit"]
    assert "financials" not in d
    assert "legal" not in d


def test_level2_adds_six_public_domains() -> None:
    d = domains_for_level(2)
    assert "competition" in d
    assert "traction" in d
    assert "capitalization" in d
    assert "legal" in d
    assert "security" in d
    assert "governance" in d
    assert "financials" not in d
    assert len(d) == 11


def test_level3_includes_financials() -> None:
    d = domains_for_level(3)
    assert "financials" in d
    assert len(d) == 12
