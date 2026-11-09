#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""Finish-line gate runner — closable rem + local E2E evidence.

Does NOT claim Gate H (independent reviewer) or production-ready.
Runs what can be automated on this stack and prints an honest scorecard.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("FINISH_LINE_OUT", "/tmp/thesis_finish_line.json"))


def run(label: str, argv: list[str], *, env: dict | None = None) -> dict:
    print(f"\n=== {label} ===", flush=True)
    merged = os.environ.copy()
    if env:
        merged.update(env)
    proc = subprocess.run(argv, cwd=ROOT, env=merged)
    print(f"exit={proc.returncode}", flush=True)
    return {"label": label, "argv": argv, "exit": proc.returncode}


def main() -> int:
    results: list[dict] = []
    results.append(run("licence_gate", [sys.executable, "scripts/licence_gate.py"]))
    results.append(run("rem_gates", [sys.executable, "scripts/run_rem_gates.py"]))
    results.append(
        run(
            "pytest_unit",
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "apps/api/tests",
                "packages/contracts/tests",
                "--ignore=apps/api/tests/test_two_firm_rls_live.py",
            ],
        )
    )

    results.append(
        run("two_firm_rls_live", [sys.executable, "scripts/smoke_rls_two_firm.py"])
    )

    if os.environ.get("FINISH_LINE_E2E", "1") not in {"0", "false", "False"}:
        results.append(
            run(
                "e2e_sondermind",
                [sys.executable, "scripts/e2e_sondermind.py"],
            )
        )

    if os.environ.get("FINISH_LINE_VALUE", "0") in {"1", "true", "True"}:
        companies = os.environ.get(
            "VALUE_COMPANIES", "Notion,Stripe,Figma,SonderMind,Lattice"
        )
        results.append(
            run(
                "validate_agent_value",
                [sys.executable, "scripts/validate_agent_value.py"],
                env={"VALUE_COMPANIES": companies},
            )
        )

    failed = [r for r in results if r.get("exit", 1) != 0]
    report = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "production_ready": False,
        "gate_h": "not_run",
        "results": results,
        "passed": len(results) - len(failed),
        "total": len(results),
        "failed_labels": [r["label"] for r in failed],
        "honest_remaining": [
            "Gate H independent verification",
            "OCR_PRODUCT_VERIFIED after sustained D4/q.docs evidence (workflow shipped)",
            "Full dependency/image SPDX reuse pin audit",
            "L2/L3 DD acceptance matrix rows (DD-04 screening still fail-closed)",
            "SearXNG multi-source diversity when upstream engines blocked",
        ],
    }
    OUT.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    print(f"wrote {OUT}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
