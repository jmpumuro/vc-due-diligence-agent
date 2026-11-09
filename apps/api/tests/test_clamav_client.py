# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""ClamAV client unit behaviour (no live clamd required)."""

from thesis_api.services.clamav import ScanResult, _sync_scan


def test_empty_payload_is_clean() -> None:
    r = _sync_scan(b"", "127.0.0.1", 1)
    assert r == ScanResult(ok=True, status="empty")


def test_unavailable_host_returns_unavailable() -> None:
    r = _sync_scan(b"hello", "127.0.0.1", 1)
    assert r.status == "unavailable"
    assert r.ok is False
