# SPDX-License-Identifier: Apache-2.0
"""OFAC ingest + potential-match unit tests (fixture mode)."""

from __future__ import annotations

import pytest

from thesis_api.services.sanctions.ofac import (
    OfacHostRefused,
    assert_treas_gov_url,
    band_for,
    fixture_path,
    load_dataset,
    match_subject,
    normalize_name,
    parse_sdn_xml,
    score_name,
)


def test_refuse_non_treas_host() -> None:
    with pytest.raises(OfacHostRefused):
        assert_treas_gov_url("https://evil.example/sdn.xml")


def test_allow_treas_hosts() -> None:
    assert assert_treas_gov_url(
        "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.XML"
    )
    assert assert_treas_gov_url("https://www.treasury.gov/ofac/downloads/sdn.xml")


def test_parse_synthetic_fixture() -> None:
    data = fixture_path().read_bytes()
    entries, publish = parse_sdn_xml(data)
    assert len(entries) >= 3
    assert publish


def test_exact_and_weak_bands() -> None:
    assert band_for(1.0) == "exact"
    assert score_name("Acme Robotics Holdings", "ACME ROBOTICS HOLDINGS") == 1.0
    assert normalize_name("  foo   bar ") == "FOO BAR"


def test_load_fixture_and_match() -> None:
    import asyncio

    entries, meta = asyncio.run(load_dataset(prefer_live=False))
    assert meta.mode == "fixture"
    assert meta.record_count >= 3
    hits = match_subject("PLINTHWICK SYNTHETIC ANALYTICS", entries)
    assert hits
    assert hits[0].band == "exact"
    assert "human review" in hits[0].disclaimer.lower()
    # Never auto-label as sanctioned in match payload
    assert all(hasattr(h, "disclaimer") for h in hits)


def test_no_match_for_clean_name() -> None:
    import asyncio

    entries, _ = asyncio.run(load_dataset(prefer_live=False))
    assert match_subject("SonderMind Inc", entries) == []
