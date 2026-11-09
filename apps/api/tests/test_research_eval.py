"""Research evaluation harness — fixture mode must be reproducible."""

from __future__ import annotations

import json
from pathlib import Path

from thesis_api.eval.research_harness import (
    HARNESS_VERSION,
    compare_to_baseline,
    evaluate_d6_fixture,
    load_d6_manifest,
)


def test_d6_fixture_eval_reproducible() -> None:
    report = evaluate_d6_fixture()
    assert report.mode == "fixture"
    assert report.harness_version == HARNESS_VERSION
    assert report.dataset_id == "d6-false-claims"
    names = {m.name for m in report.metrics}
    assert "contradiction_recall" in names
    assert "syndicated_not_counted_independent" in names
    # Structural expectations for the fixture harness
    by_name = {m.name: m for m in report.metrics}
    assert by_name["contradiction_recall"].value == 1.0
    assert by_name["syndicated_not_counted_independent"].value == 1.0
    assert by_name["contradiction_preserved_low_rank"].value == 1.0
    assert any(
        "ci-local" in s or "Pages" in s or "D6_FIXTURE" in s for s in report.skipped
    )
    # Second run identical metric values
    report2 = evaluate_d6_fixture()
    assert [m.value for m in report.metrics] == [m.value for m in report2.metrics]


def test_baseline_comparison_detects_regression() -> None:
    report = evaluate_d6_fixture()
    baseline = report.to_dict()
    # Simulate regression
    for m in baseline["metrics"]:
        if m["name"] == "contradiction_recall":
            m["value"] = 1.0
    # Current lower than baseline
    from dataclasses import replace
    from thesis_api.eval.research_harness import Metric

    degraded = replace(
        report,
        metrics=[
            Metric("contradiction_recall", 0.5, 1, 2)
            if m.name == "contradiction_recall"
            else m
            for m in report.metrics
        ],
    )
    regs = compare_to_baseline(degraded, baseline)
    assert any(r["metric"] == "contradiction_recall" for r in regs)


def test_manifest_loads() -> None:
    m = load_d6_manifest()
    assert m.get("synthetic") is True
    assert len(m.get("claims") or []) >= 5


def test_write_baseline_shape(tmp_path: Path) -> None:
    from thesis_api.eval.research_harness import write_report

    report = evaluate_d6_fixture()
    out = tmp_path / "report.json"
    write_report(report, out)
    data = json.loads(out.read_text())
    assert data["harness_version"] == HARNESS_VERSION
    assert (tmp_path / "report.txt").exists()
