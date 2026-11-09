#!/usr/bin/env python3
"""CI entrypoint: fixture research eval + baseline regression check."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from thesis_api.eval.research_harness import (  # noqa: E402
    compare_to_baseline,
    evaluate_d6_fixture,
    evaluate_d6_live_local,
    write_report,
)


def main() -> int:
    import os

    out_dir = ROOT / "baselines" / "last_run"
    report = evaluate_d6_fixture()
    write_report(report, out_dir / "research_eval.json")
    print(report.human_summary())

    baseline_path = ROOT / "baselines" / "research_eval_baseline.json"
    baseline = json.loads(baseline_path.read_text())
    regressions = compare_to_baseline(report, baseline)
    if regressions:
        print("REGRESSIONS:", json.dumps(regressions, indent=2))
        return 1
    print("No regressions vs baseline.")
    for s in report.skipped:
        print("SKIP:", s)

    # Optional ci-local HTTP check (compose d6-fixture). Never invents Pages URL.
    if os.environ.get("D6_SKIP_LIVE", "").strip() not in {"1", "true"}:
        live = evaluate_d6_live_local()
        write_report(live, out_dir / "research_eval_live_local.json")
        print(live.human_summary())
        if live.dataset_version == "unreachable":
            print("WARN: d6-fixture unreachable (start with: docker compose up -d d6-fixture)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
