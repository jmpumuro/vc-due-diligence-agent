"""Deterministic financial calculations — ddcalc@1. No I/O; Decimal only."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from thesis_contracts.dd import CalculationResult, InputRef, PeriodRange

FORMULA_VERSION = "ddcalc@1"
ZERO = Decimal("0")


def _period(start: date, end: date, granularity: str = "month") -> PeriodRange:
    return PeriodRange(start=start, end=end, granularity=granularity)  # type: ignore[arg-type]


def _input(
    name: str,
    value: Decimal,
    unit: str,
    period: PeriodRange,
    *,
    claim_id: UUID | None = None,
    financial_table_id: UUID | None = None,
) -> InputRef:
    return InputRef(
        name=name,
        value=value,
        unit=unit,
        period=period,
        claim_id=claim_id,
        financial_table_id=financial_table_id or (None if claim_id else uuid4()),
    )


def revenue_growth(
    revenue_t: Decimal | None,
    revenue_prev: Decimal | None,
    *,
    period: PeriodRange,
    table_id: UUID | None = None,
) -> CalculationResult:
    missing: list[str] = []
    if revenue_t is None:
        missing.append("revenue_t")
    if revenue_prev is None:
        missing.append("revenue_prev")
    if missing or revenue_prev == ZERO:
        return CalculationResult(
            calculation_id=uuid4(),
            metric="revenue_growth",
            formula_version=FORMULA_VERSION,
            status="not_computable",
            value=None,
            unit="percent",
            currency=None,
            period=period,
            inputs=[],
            assumptions=[],
            missing_inputs=missing or ["revenue_prev_zero"],
        )
    assert revenue_t is not None and revenue_prev is not None
    value = (revenue_t - revenue_prev) / revenue_prev
    inputs = [
        _input("revenue_t", revenue_t, "currency", period, financial_table_id=table_id),
        _input("revenue_prev", revenue_prev, "currency", period, financial_table_id=table_id),
    ]
    return CalculationResult(
        calculation_id=uuid4(),
        metric="revenue_growth",
        formula_version=FORMULA_VERSION,
        status="computed",
        value=value,
        unit="percent",
        currency="USD",
        period=period,
        inputs=inputs,
        assumptions=["same currency and basis"],
    )


def gross_margin(
    revenue: Decimal | None,
    cost_of_revenue: Decimal | None,
    *,
    period: PeriodRange,
    table_id: UUID | None = None,
) -> CalculationResult:
    missing = [n for n, v in [("revenue", revenue), ("cost_of_revenue", cost_of_revenue)] if v is None]
    if missing or revenue == ZERO:
        return CalculationResult(
            calculation_id=uuid4(),
            metric="gross_margin",
            formula_version=FORMULA_VERSION,
            status="not_computable",
            value=None,
            unit="percent",
            currency=None,
            period=period,
            inputs=[],
            assumptions=[],
            missing_inputs=missing or ["revenue_zero"],
        )
    assert revenue is not None and cost_of_revenue is not None
    value = (revenue - cost_of_revenue) / revenue
    return CalculationResult(
        calculation_id=uuid4(),
        metric="gross_margin",
        formula_version=FORMULA_VERSION,
        status="computed",
        value=value,
        unit="percent",
        currency="USD",
        period=period,
        inputs=[
            _input("revenue", revenue, "currency", period, financial_table_id=table_id),
            _input("cost_of_revenue", cost_of_revenue, "currency", period, financial_table_id=table_id),
        ],
        assumptions=["cost-of-revenue definition from source"],
    )


def net_burn(
    cash_start: Decimal | None,
    cash_end: Decimal | None,
    financing_inflows: Decimal | None = ZERO,
    *,
    period: PeriodRange,
    table_id: UUID | None = None,
) -> CalculationResult:
    missing = [
        n
        for n, v in [
            ("cash_start", cash_start),
            ("cash_end", cash_end),
        ]
        if v is None
    ]
    if missing:
        return CalculationResult(
            calculation_id=uuid4(),
            metric="net_burn",
            formula_version=FORMULA_VERSION,
            status="not_computable",
            value=None,
            unit="currency",
            currency="USD",
            period=period,
            inputs=[],
            assumptions=[],
            missing_inputs=missing,
        )
    assert cash_start is not None and cash_end is not None
    fin = financing_inflows or ZERO
    value = cash_start - cash_end - fin
    return CalculationResult(
        calculation_id=uuid4(),
        metric="net_burn",
        formula_version=FORMULA_VERSION,
        status="computed",
        value=value,
        unit="currency",
        currency="USD",
        period=period,
        inputs=[
            _input("cash_start", cash_start, "currency", period, financial_table_id=table_id),
            _input("cash_end", cash_end, "currency", period, financial_table_id=table_id),
            _input("financing_inflows", fin, "currency", period, financial_table_id=table_id),
        ],
        assumptions=["financing inflows excluded from burn"],
    )


def runway(
    cash_latest: Decimal | None,
    avg_net_burn: Decimal | None,
    *,
    period: PeriodRange,
    table_id: UUID | None = None,
) -> CalculationResult:
    missing = [
        n
        for n, v in [("cash_latest", cash_latest), ("avg_net_burn", avg_net_burn)]
        if v is None
    ]
    if missing:
        return CalculationResult(
            calculation_id=uuid4(),
            metric="runway",
            formula_version=FORMULA_VERSION,
            status="not_computable",
            value=None,
            unit="months",
            currency=None,
            period=period,
            inputs=[],
            assumptions=[],
            missing_inputs=missing,
        )
    assert cash_latest is not None and avg_net_burn is not None
    if avg_net_burn <= ZERO:
        return CalculationResult(
            calculation_id=uuid4(),
            metric="runway",
            formula_version=FORMULA_VERSION,
            status="not_computable",
            value=None,
            unit="months",
            currency=None,
            period=period,
            inputs=[],
            assumptions=["cash-flow positive in period"],
            missing_inputs=["avg_net_burn_non_positive"],
        )
    value = cash_latest / avg_net_burn
    return CalculationResult(
        calculation_id=uuid4(),
        metric="runway",
        formula_version=FORMULA_VERSION,
        status="computed",
        value=value,
        unit="months",
        currency=None,
        period=period,
        inputs=[
            _input("cash_latest", cash_latest, "currency", period, financial_table_id=table_id),
            _input("avg_net_burn", avg_net_burn, "currency", period, financial_table_id=table_id),
        ],
        assumptions=["trailing 3-month average net burn"],
    )


def arr_vs_mrr(
    arr_reported: Decimal | None,
    mrr_latest: Decimal | None,
    *,
    period: PeriodRange,
    table_id: UUID | None = None,
    tolerance: Decimal = Decimal("0.05"),
) -> CalculationResult:
    missing = [
        n
        for n, v in [("arr_reported", arr_reported), ("mrr_latest", mrr_latest)]
        if v is None
    ]
    if missing:
        return CalculationResult(
            calculation_id=uuid4(),
            metric="arr_mrr_reconciliation",
            formula_version=FORMULA_VERSION,
            status="not_computable",
            value=None,
            unit="percent",
            currency=None,
            period=period,
            inputs=[],
            assumptions=[],
            missing_inputs=missing,
        )
    assert arr_reported is not None and mrr_latest is not None
    implied = mrr_latest * Decimal("12")
    if implied == ZERO:
        diff = Decimal("1") if arr_reported != ZERO else ZERO
    else:
        diff = abs(arr_reported - implied) / implied
    flagged = diff > tolerance
    return CalculationResult(
        calculation_id=uuid4(),
        metric="arr_mrr_reconciliation",
        formula_version=FORMULA_VERSION,
        status="flagged" if flagged else "computed",
        value=diff,
        unit="percent",
        currency="USD",
        period=period,
        inputs=[
            _input("arr_reported", arr_reported, "currency", period, financial_table_id=table_id),
            _input("mrr_latest", mrr_latest, "currency", period, financial_table_id=table_id),
            _input("implied_arr", implied, "currency", period, financial_table_id=table_id),
        ],
        assumptions=["ARR vs MRR×12"],
        validation_issues=["difference_over_5_percent"] if flagged else [],
    )
