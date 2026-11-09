#!/usr/bin/env python3
"""D6 local fixture HTTP smoke — never invents a public Pages URL.

Decision: compose service `d6-fixture` (nginx) serves fixtures/d6-site/false-claims
at http://localhost:8090. Public Pages deploy remains optional and unauthorized.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

base = os.environ.get("D6_FIXTURE_URL", "http://localhost:8090").rstrip("/")


def fetch(path: str) -> bytes:
    req = urllib.request.Request(
        f"{base}{path}",
        headers={"User-Agent": "ThesisDiligenceBot/0.1 (D6 local fixture smoke)"},
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read()


def main() -> int:
    try:
        index = fetch("/").decode("utf-8", errors="replace")
        manifest_raw = fetch("/manifest.json")
        manifest = json.loads(manifest_raw.decode("utf-8"))
    except urllib.error.URLError as exc:
        print(f"status=failed cannot reach {base}: {exc}")
        print("hint: docker compose up -d d6-fixture")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"status=failed {exc}")
        return 1

    if "claims" not in manifest:
        print("status=failed manifest missing claims")
        return 1
    if len(index) < 20:
        print("status=failed index.html too short")
        return 1

    # Spot-check one evidence page if listed (evidence may be str or list)
    claims = manifest.get("claims") or []
    for c in claims:
        evid = c.get("evidence")
        if not evid:
            continue
        first = evid[0] if isinstance(evid, list) else evid
        path = first if str(first).startswith("/") else f"/{first}"
        try:
            body = fetch(path)
            if len(body) < 10:
                print(f"status=failed empty evidence {path}")
                return 1
        except Exception as exc:  # noqa: BLE001
            print(f"status=failed evidence {path}: {exc}")
            return 1
        break

    print(f"status=ok base={base} claims={len(claims)} mode=ci-local")
    print("public_pages=not_authorized (REM-P2-01 optional)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
