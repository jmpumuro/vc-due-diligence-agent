#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""REM-P1-06 / D5 licence gate — fail closed on missing Apache files or seeded GPL deps.

This is a first-party gate (not a full SPDX/reuse audit). It:
1. Requires LICENSE + NOTICE at repo root with Apache-2.0 markers
2. Scans first-party Python/TS package metadata for forbidden copyleft when listed
3. Optionally fails if a known GPL fixture marker is present under fixtures/licence-gate/

Exit 0 = pass. Exit 1 = fail.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = ("GPL-3.0", "AGPL-3.0", "SSPL", "BUSL")


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    license_path = ROOT / "LICENSE"
    notice_path = ROOT / "NOTICE"
    if not license_path.is_file():
        fail("LICENSE missing")
    if not notice_path.is_file():
        fail("NOTICE missing")
    lic = license_path.read_text(encoding="utf-8", errors="replace")
    if "Apache License" not in lic and "Apache-2.0" not in lic:
        fail("LICENSE does not look like Apache-2.0")
    notice = notice_path.read_text(encoding="utf-8", errors="replace")
    if "Thesis" not in notice:
        fail("NOTICE missing Thesis attribution")

    # Seeded GPL fixture must cause failure when intentionally present for CI self-test.
    poison = ROOT / "fixtures" / "licence-gate" / "poison-gpl.json"
    if poison.is_file():
        data = json.loads(poison.read_text(encoding="utf-8"))
        lic_id = str(data.get("license") or data.get("licence") or "")
        if any(f in lic_id for f in FORBIDDEN):
            fail(f"forbidden licence fixture present: {lic_id} ({poison})")

    # First-party package.json / pyproject must not declare forbidden licences.
    for meta in ROOT.glob("**/package.json"):
        if "node_modules" in meta.parts:
            continue
        data = json.loads(meta.read_text(encoding="utf-8"))
        declared = str(data.get("license") or "")
        if any(f in declared for f in FORBIDDEN):
            fail(f"{meta.relative_to(ROOT)} declares {declared}")

    for meta in ROOT.glob("**/pyproject.toml"):
        text = meta.read_text(encoding="utf-8")
        for f in FORBIDDEN:
            if f'license = "{f}"' in text or f"license = '{f}'" in text:
                fail(f"{meta.relative_to(ROOT)} declares {f}")

    # Require SPDX markers on a first-party seed set (expand over time).
    required_spdx = [
        ROOT / "apps" / "api" / "src" / "thesis_api" / "services" / "outbox.py",
        ROOT / "apps" / "api" / "src" / "thesis_api" / "tenant_rls.py",
        ROOT / "apps" / "api" / "src" / "thesis_api" / "tenant.py",
        ROOT / "apps" / "api" / "src" / "thesis_api" / "services" / "policy_provider.py",
        ROOT / "apps" / "api" / "src" / "thesis_api" / "services" / "retention.py",
        ROOT / "apps" / "api" / "src" / "thesis_api" / "services" / "readiness.py",
        ROOT / "apps" / "api" / "src" / "thesis_api" / "services" / "clamav.py",
        ROOT / "apps" / "api" / "src" / "thesis_api" / "services" / "object_store.py",
        ROOT / "apps" / "api" / "src" / "thesis_api" / "services" / "worker_docs.py",
        ROOT / "apps" / "api" / "src" / "thesis_api" / "temporal_app" / "docs_activities.py",
        ROOT / "apps" / "api" / "src" / "thesis_api" / "worker_docs_queue.py",
        ROOT / "packages" / "contracts" / "src" / "thesis_contracts" / "lifecycle.py",
        ROOT / "packages" / "contracts" / "src" / "thesis_contracts" / "grounding.py",
        ROOT / "scripts" / "licence_gate.py",
        ROOT / "scripts" / "run_rem_gates.py",
    ]
    for path in required_spdx:
        if not path.is_file():
            fail(f"missing first-party file for SPDX check: {path.relative_to(ROOT)}")
        head = path.read_text(encoding="utf-8", errors="replace")[:800]
        if "SPDX-License-Identifier: Apache-2.0" not in head:
            fail(f"missing SPDX-License-Identifier on {path.relative_to(ROOT)}")

    # Aggregated third-party notices (D5-02). Content must reference NOTICE sources — do not invent.
    third = ROOT / "THIRD_PARTY_NOTICES.md"
    if not third.is_file():
        fail("THIRD_PARTY_NOTICES.md missing")
    third_text = third.read_text(encoding="utf-8", errors="replace")
    if "SearXNG" not in third_text or "Apache-2.0" not in third_text:
        fail("THIRD_PARTY_NOTICES.md incomplete (expect SearXNG + Apache-2.0 markers)")

    print("OK: licence gate passed (LICENSE/NOTICE/THIRD_PARTY_NOTICES; SPDX seed; no forbidden first-party markers)")


if __name__ == "__main__":
    main()
