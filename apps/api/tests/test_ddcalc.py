"""ddcalc@1 property and golden tests — no I/O."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

from thesis_api.services.ddcalc import (
    FORMULA_VERSION,
    arr_vs_mrr,
    gross_margin,
    net_burn,
    revenue_growth,
    runway,
)
from thesis_contracts.dd import PeriodRange


def _period() -> PeriodRange:
    return PeriodRange(start=date(2024, 1, 1), end=date(2024, 1, 31), granularity="month")


def test_revenue_growth_constant_series_is_zero() -> None:
    tid = uuid4()
    r = revenue_growth(Decimal("100"), Decimal("100"), period=_period(), table_id=tid)
    assert r.status == "computed"
    assert r.value == Decimal("0")
    assert r.formula_version == FORMULA_VERSION


def test_revenue_growth_missing_inputs() -> None:
    r = revenue_growth(None, Decimal("10"), period=_period())
    assert r.status == "not_computable"
    assert "revenue_t" in r.missing_inputs
    assert r.value is None


def test_gross_margin() -> None:
    r = gross_margin(Decimal("200"), Decimal("50"), period=_period(), table_id=uuid4())
    assert r.status == "computed"
    assert r.value == Decimal("0.75")


def test_runway_not_computed_when_non_positive_burn() -> None:
    r = runway(Decimal("1000"), Decimal("0"), period=_period(), table_id=uuid4())
    assert r.status == "not_computable"
    assert "avg_net_burn_non_positive" in r.missing_inputs


def test_runway_months() -> None:
    r = runway(Decimal("900"), Decimal("100"), period=_period(), table_id=uuid4())
    assert r.status == "computed"
    assert r.value == Decimal("9")


def test_net_burn_excludes_financing() -> None:
    r = net_burn(
        Decimal("100"),
        Decimal("80"),
        financing_inflows=Decimal("10"),
        period=_period(),
        table_id=uuid4(),
    )
    assert r.status == "computed"
    assert r.value == Decimal("10")


def test_arr_mrr_flags_over_tolerance() -> None:
    r = arr_vs_mrr(Decimal("100"), Decimal("5"), period=_period(), table_id=uuid4())
    # implied 60 vs 100 → ~66% diff
    assert r.status == "flagged"
    assert r.validation_issues
