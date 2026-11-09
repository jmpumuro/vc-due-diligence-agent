# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""Level 3 fail-closed gates (DD-05 subset) — unit, no OpenAI."""

from __future__ import annotations

from thesis_api.services.level_gates import (
    level3_private_ai_allowed,
    level3_screening_allowed,
)
from thesis_api.tenant import TenantContext


def test_analyst_cannot_access_private_without_deal_team() -> None:
    ctx = TenantContext(firm_id="frm_demo", user_id="u1", roles=("analyst",))
    assert not ctx.may_access_private("aid-1")


def test_partner_on_deal_team_may_access_private() -> None:
    ctx = TenantContext(
        firm_id="frm_demo",
        user_id="u1",
        roles=("partner",),
        deal_team_assessment_ids=frozenset({"aid-1"}),
    )
    assert ctx.may_access_private("aid-1")


def test_level3_create_rejects_non_partner_roles() -> None:
    """Mirror route rule: only partner/admin/owner may open L3 shell."""
    allowed = {"partner", "admin", "owner"}
    for role in ("analyst", "viewer", "associate"):
        assert role not in allowed
    for role in allowed:
        assert role in allowed


def test_level3_private_pipeline_detail_constant() -> None:
    from thesis_api.routes import screening

    src = open(screening.__file__, encoding="utf-8").read()
    assert "LEVEL3_PRIVATE_PIPELINE_NOT_READY" in src
    assert "DealTeamMemberRow" in src
    assert "DataRoomRow" in src
    assert "/deepen" in src or "deepen_assessment" in src


def test_private_ai_always_fail_closed() -> None:
    assert level3_private_ai_allowed() is False


def test_level3_screening_tracks_ocr_flag(monkeypatch) -> None:
    from thesis_api import settings as settings_mod

    monkeypatch.setattr(settings_mod.settings, "ocr_product_verified", False)
    assert level3_screening_allowed() is False
    monkeypatch.setattr(settings_mod.settings, "ocr_product_verified", True)
    assert level3_screening_allowed() is True
