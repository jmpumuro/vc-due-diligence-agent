"""Stage 8 RLS / GUC scaffolding checks (no live Postgres required)."""

from __future__ import annotations

from pathlib import Path

import pytest

from thesis_api.tenant_rls import activate_tenant_rls, set_app_role, set_tenant_guc


def test_rls_helpers_importable() -> None:
    assert callable(set_tenant_guc)
    assert callable(set_app_role)
    assert callable(activate_tenant_rls)


def test_rls_migration_lists_firm_tables() -> None:
    text = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0006_rls_notifications.py"
    ).read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in text
    assert "thesis_app" in text
    assert "notifications" in text
    assert "assessments" in text
    assert "claims" in text


def test_rls_role_grant_migration_exists() -> None:
    text = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "0007_rls_role_grant.py"
    ).read_text(encoding="utf-8")
    assert "GRANT thesis_app TO thesis" in text


def test_set_app_role_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    import asyncio

    monkeypatch.setattr("thesis_api.tenant_rls.settings.enforce_rls_role", False)

    class _Sess:
        async def execute(self, *_a, **_k):  # noqa: ANN001
            raise AssertionError("should not execute when disabled")

    assert asyncio.run(set_app_role(_Sess())) is False  # type: ignore[arg-type]
