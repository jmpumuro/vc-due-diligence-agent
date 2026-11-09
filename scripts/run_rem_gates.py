#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""Run industry-default rem gate smokes (no owner prompts)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(label: str, argv: list[str]) -> int:
    print(f"\n=== {label} ===")
    proc = subprocess.run(argv, cwd=ROOT)
    print(f"exit={proc.returncode}")
    return proc.returncode


def main() -> int:
    codes = []
    codes.append(run("B1 SeaweedFS", [sys.executable, "scripts/smoke_b1_seaweed.py"]))
    codes.append(run("D6 local fixture", [sys.executable, "scripts/smoke_d6_local.py"]))
    codes.append(
        run(
            "OFAC unit + retention + D1 pytest",
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "apps/api/tests/test_ofac.py",
                "apps/api/tests/test_retention.py",
                "apps/api/tests/test_p0_gates.py",
                "apps/api/tests/test_llm_gateway.py",
                "apps/api/tests/test_research_eval.py",
                "apps/api/tests/test_level3_gates.py",
            ],
        )
    )
    codes.append(run("licence_gate", [sys.executable, "scripts/licence_gate.py"]))
    failed = [c for c in codes if c != 0]
    print(f"\nsummary passed={len(codes) - len(failed)}/{len(codes)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
