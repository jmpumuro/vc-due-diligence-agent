#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""Smoke two-firm RLS via Compose API one-shot (REM-P0-02)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

INNER = (
    "pip install -q pytest pytest-asyncio >/dev/null && "
    "python -m pytest -q tests/test_two_firm_rls_live.py"
)


def main() -> int:
    test_src = ROOT / "apps" / "api" / "tests" / "test_two_firm_rls_live.py"
    cmd = [
        "docker",
        "compose",
        "run",
        "--rm",
        "--no-deps",
        "-v",
        f"{test_src}:/app/apps/api/tests/test_two_firm_rls_live.py:ro",
        "-e",
        "LIVE_RLS=1",
        "-e",
        "DATABASE_URL=postgresql+asyncpg://thesis:thesis@postgres:5432/thesis",
        "api",
        "sh",
        "-c",
        INNER,
    ]
    print("docker compose run … api sh -c <pytest two-firm RLS>")
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
