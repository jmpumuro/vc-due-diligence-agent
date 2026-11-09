# SPDX-License-Identifier: Apache-2.0
"""DeletionCertificate dry-run default tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from thesis_api.services.retention import execute_deletion, plan_deletion


def test_plan_is_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RETENTION_CERT_DIR", str(tmp_path))
    monkeypatch.delenv("RETENTION_DESTRUCTIVE_DELETE", raising=False)
    cert = plan_deletion(
        firm_id="frm_demo",
        data_room_ids=["dr1"],
        retention_record_ids=["rr1"],
        object_keys=["frm_demo/a/*"],
    )
    assert cert.mode == "dry_run"
    assert (tmp_path / f"{cert.certificate_id}.json").is_file()
    again = execute_deletion(cert)
    assert again.mode == "dry_run"
    assert again.blocked_reasons


def test_execute_when_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RETENTION_CERT_DIR", str(tmp_path))
    monkeypatch.setenv("RETENTION_DESTRUCTIVE_DELETE", "true")
    cert = plan_deletion(
        firm_id="frm_demo",
        data_room_ids=[],
        retention_record_ids=[],
        object_keys=[],
    )
    done = execute_deletion(cert)
    assert done.mode.startswith("executed")
    assert done.objects_deleted == []
