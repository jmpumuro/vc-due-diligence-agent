from thesis_api.services.financial_validation import validate_financial_tables


def test_empty_tables_require_validation() -> None:
    out = validate_financial_tables([])
    assert out["status"] == "VALIDATION_REQUIRED"


def test_balanced_sheet_validates() -> None:
    out = validate_financial_tables(
        [{"kind": "balance_sheet", "assets": "100", "liabilities": "40", "equity": "60"}]
    )
    assert out["status"] == "VALIDATED"


def test_imbalanced_sheet_requires_validation() -> None:
    out = validate_financial_tables(
        [{"kind": "balance_sheet", "assets": "100", "liabilities": "40", "equity": "50"}]
    )
    assert out["status"] == "VALIDATION_REQUIRED"


def test_income_margin_via_ddcalc() -> None:
    out = validate_financial_tables([{"kind": "income", "revenue": "100", "cogs": "40"}])
    assert out["status"] == "VALIDATED"
    assert out["findings"][0]["code"] == "MARGIN_COMPUTED"
