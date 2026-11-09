"""Financial table validation queue using ddcalc (Stage 6, no OCR required)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from thesis_api.services.ddcalc import arr_vs_mrr, gross_margin, revenue_growth
from thesis_contracts.dd import PeriodRange


def _period() -> PeriodRange:
    return PeriodRange(start=date(2025, 1, 1), end=date(2025, 12, 31), granularity="year")


def validate_financial_tables(tables: list[dict[str, Any]]) -> dict[str, Any]:
    """Return validation findings. Empty/invalid inputs → VALIDATION_REQUIRED."""
    findings: list[dict[str, Any]] = []
    if not tables:
        return {
            "status": "VALIDATION_REQUIRED",
            "findings": [{"code": "NO_TABLES", "message": "No financial tables provided"}],
        }

    period = _period()
    for idx, table in enumerate(tables):
        kind = str(table.get("kind") or "unknown")
        if kind == "income":
            result = gross_margin(
                Decimal(str(table["revenue"])) if "revenue" in table else None,
                Decimal(str(table["cogs"])) if "cogs" in table else None,
                period=period,
            )
            findings.append(
                {
                    "table_index": idx,
                    "kind": kind,
                    "metric": result.metric,
                    "status": result.status,
                    "value": str(result.value) if result.value is not None else None,
                    "ok": result.status == "computed",
                    "code": "MARGIN_COMPUTED" if result.status == "computed" else "MARGIN_NOT_COMPUTABLE",
                }
            )
        elif kind == "growth":
            result = revenue_growth(
                Decimal(str(table["current"])) if "current" in table else None,
                Decimal(str(table["prior"])) if "prior" in table else None,
                period=period,
            )
            findings.append(
                {
                    "table_index": idx,
                    "kind": kind,
                    "metric": result.metric,
                    "status": result.status,
                    "value": str(result.value) if result.value is not None else None,
                    "ok": result.status == "computed",
                    "code": "GROWTH_COMPUTED" if result.status == "computed" else "GROWTH_NOT_COMPUTABLE",
                }
            )
        elif kind == "arr_mrr":
            result = arr_vs_mrr(
                Decimal(str(table["arr"])) if "arr" in table else None,
                Decimal(str(table["mrr"])) if "mrr" in table else None,
                period=period,
            )
            findings.append(
                {
                    "table_index": idx,
                    "kind": kind,
                    "metric": result.metric,
                    "status": result.status,
                    "value": str(result.value) if result.value is not None else None,
                    "ok": result.status == "computed",
                    "code": "ARR_MRR_OK" if result.status == "computed" else "ARR_MRR_ISSUE",
                }
            )
        elif kind == "balance_sheet":
            assets = Decimal(str(table.get("assets", "0")))
            liabilities = Decimal(str(table.get("liabilities", "0")))
            equity = Decimal(str(table.get("equity", "0")))
            ok = assets == liabilities + equity
            findings.append(
                {
                    "table_index": idx,
                    "kind": kind,
                    "ok": ok,
                    "code": "BALANCE_SHEET_OK" if ok else "BALANCE_SHEET_IMBALANCE",
                }
            )
        else:
            findings.append(
                {
                    "table_index": idx,
                    "kind": kind,
                    "ok": False,
                    "code": "UNKNOWN_TABLE_KIND",
                }
            )

    if any(not f.get("ok", False) for f in findings):
        return {"status": "VALIDATION_REQUIRED", "findings": findings}
    return {"status": "VALIDATED", "findings": findings}
