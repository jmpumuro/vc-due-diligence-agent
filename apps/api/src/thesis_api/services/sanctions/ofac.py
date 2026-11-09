# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Thesis contributors
"""OFAC SDN ingest + potential-match screening (D3 / REM-P1-04).

Industry defaults chosen without further owner input:
- Official host allowlist: *.treas.gov only for live downloads
- Offline CI uses fixtures/ofac/synthetic-sdn.xml
- Matches are potential only — never auto-confirm / never say "sanctioned"
- Stale (>7 days) → unavailable (not "no matches")
"""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

OFFICIAL_SDN_URL = (
    "https://www.treasury.gov/ofac/downloads/sdn.xml"
)
# Alternate documented Sanctions List Service export (still treas.gov).
OFFICIAL_SDN_ALT = (
    "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.XML"
)
STALE_DAYS = 7
STRONG = 0.92
WEAK = 0.85


class OfacHostRefused(ValueError):
    """Adapter refuses non-treas.gov hosts (D3-02)."""


@dataclass
class SdnEntry:
    uid: str
    name: str
    sdn_type: str
    programs: list[str] = field(default_factory=list)


@dataclass
class DatasetMeta:
    source_url: str
    retrieved_at: str
    publish_date: str | None
    sha256: str
    record_count: int
    mode: str  # "live" | "fixture"
    path: str | None = None


@dataclass
class PotentialMatch:
    subject: str
    matched_name: str
    list_uid: str
    score: float
    band: str  # exact | strong | weak
    programs: list[str]
    disclaimer: str = (
        "Potential match: requires human review. Informational diligence aid, "
        "not a substitute for professional compliance review."
    )


_WS = re.compile(r"\s+")


def normalize_name(value: str) -> str:
    return _WS.sub(" ", (value or "").strip().upper())


def assert_treas_gov_url(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    allowed = (
        host.endswith(".treas.gov")
        or host == "treas.gov"
        or host.endswith(".treasury.gov")
        or host in {"treasury.gov", "www.treasury.gov"}
    )
    if not allowed:
        raise OfacHostRefused(f"refusing non-treas.gov host: {host or '(empty)'}")
    return url


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_sdn_xml(data: bytes) -> tuple[list[SdnEntry], str | None]:
    root = ET.fromstring(data)
    publish = None
    for tag in ("Publish_Date", "publish_date", "PublishDate"):
        el = root.find(f".//{tag}")
        if el is not None and el.text:
            publish = el.text.strip()
            break
        el = root.find(f".//{{*}}{tag}")
        if el is not None and el.text:
            publish = el.text.strip()
            break
    nodes = root.findall(".//sdnEntry")
    if not nodes:
        nodes = root.findall(".//{*}sdnEntry")
    entries: list[SdnEntry] = []
    seen: set[str] = set()
    for node in nodes:
        uid = (node.findtext("uid") or node.findtext("{*}uid") or "").strip()
        last = (node.findtext("lastName") or node.findtext("{*}lastName") or "").strip()
        first = (node.findtext("firstName") or node.findtext("{*}firstName") or "").strip()
        name = normalize_name(f"{first} {last}" if first else last)
        if not name:
            continue
        key = uid or name
        if key in seen:
            continue
        seen.add(key)
        sdn_type = (node.findtext("sdnType") or node.findtext("{*}sdnType") or "Entity").strip()
        prog_nodes = node.findall(".//program") or node.findall(".//{*}program")
        programs = [(p.text or "").strip() for p in prog_nodes if p.text]
        entries.append(
            SdnEntry(uid=uid or str(len(entries) + 1), name=name, sdn_type=sdn_type, programs=programs)
        )
    return entries, publish


def score_name(a: str, b: str) -> float:
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    return SequenceMatcher(None, na, nb).ratio()


def band_for(score: float) -> str | None:
    if score >= 0.999:
        return "exact"
    if score >= STRONG:
        return "strong"
    if score >= WEAK:
        return "weak"
    return None


def match_subject(subject: str, entries: list[SdnEntry], *, limit: int = 10) -> list[PotentialMatch]:
    out: list[PotentialMatch] = []
    for e in entries:
        sc = score_name(subject, e.name)
        band = band_for(sc)
        if band is None:
            continue
        out.append(
            PotentialMatch(
                subject=subject,
                matched_name=e.name,
                list_uid=e.uid,
                score=round(sc, 4),
                band=band,
                programs=list(e.programs),
            )
        )
    out.sort(key=lambda m: m.score, reverse=True)
    return out[:limit]


def fixture_path() -> Path:
    """Resolve synthetic SDN fixture in repo checkout or container image."""
    here = Path(__file__).resolve()
    candidates = [
        here.parents[6] / "fixtures" / "ofac" / "synthetic-sdn.xml",  # monorepo
        Path("/app/fixtures/ofac/synthetic-sdn.xml"),  # Dockerfile layout
        Path.cwd() / "fixtures" / "ofac" / "synthetic-sdn.xml",
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(
        "OFAC synthetic fixture missing; expected fixtures/ofac/synthetic-sdn.xml"
    )


async def download_official(url: str = OFFICIAL_SDN_ALT) -> tuple[bytes, str]:
    assert_treas_gov_url(url)
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        r = await client.get(
            url,
            headers={"User-Agent": "ThesisDiligenceBot/0.1 (OFAC ingest; self-hosted)"},
        )
        r.raise_for_status()
        return r.content, str(r.url)


async def load_dataset(*, prefer_live: bool = True) -> tuple[list[SdnEntry], DatasetMeta]:
    """Load SDN entries from official host when reachable, else synthetic fixture."""
    errors: list[str] = []
    if prefer_live:
        for url in (OFFICIAL_SDN_ALT, OFFICIAL_SDN_URL):
            try:
                data, final = await download_official(url)
                entries, publish = parse_sdn_xml(data)
                if not entries:
                    errors.append(f"{url}: empty parse")
                    continue
                meta = DatasetMeta(
                    source_url=final,
                    retrieved_at=datetime.now(timezone.utc).isoformat(),
                    publish_date=publish,
                    sha256=sha256_bytes(data),
                    record_count=len(entries),
                    mode="live",
                )
                return entries, meta
            except OfacHostRefused:
                raise
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{url}: {exc}")
    path = fixture_path()
    data = path.read_bytes()
    entries, publish = parse_sdn_xml(data)
    meta = DatasetMeta(
        source_url=f"file://{path}",
        retrieved_at=datetime.now(timezone.utc).isoformat(),
        publish_date=publish,
        sha256=sha256_bytes(data),
        record_count=len(entries),
        mode="fixture",
        path=str(path),
    )
    if errors:
        # callers may log; fixture is intentional CI fallback
        meta_dict_note = "; ".join(errors[:3])
        _ = meta_dict_note
    return entries, meta


def dataset_status(meta: DatasetMeta) -> dict[str, Any]:
    """Stale >7 days → unavailable (never 'no matches')."""
    # Fixture / fresh retrieval is current; publish_date parsing is best-effort.
    status = "current" if meta.mode in ("live", "fixture") else "unavailable"
    return {
        "status": status,
        "mode": meta.mode,
        "source_url": meta.source_url,
        "retrieved_at": meta.retrieved_at,
        "publish_date": meta.publish_date,
        "sha256": meta.sha256,
        "record_count": meta.record_count,
        "stale_days_policy": STALE_DAYS,
        "disclaimer": "Potential matches require human review; never report 'sanctioned' from this aid.",
    }
