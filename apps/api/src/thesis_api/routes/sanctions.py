# SPDX-License-Identifier: Apache-2.0
"""OFAC dataset status + potential-match screening (D3)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from thesis_api.services.sanctions.ofac import (
    OfacHostRefused,
    assert_treas_gov_url,
    dataset_status,
    load_dataset,
    match_subject,
)

router = APIRouter(tags=["sanctions"])

# Process-local cache for last successful load (fixture or live).
_CACHE: dict = {}


class ScreenBody(BaseModel):
    subjects: list[str] = Field(min_length=1, max_length=50)
    prefer_live: bool = False


@router.get("/sanctions/dataset")
async def get_dataset_status(prefer_live: bool = Query(default=False)) -> dict:
    try:
        entries, meta = await load_dataset(prefer_live=prefer_live)
    except OfacHostRefused as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _CACHE["entries"] = entries
    _CACHE["meta"] = meta
    return dataset_status(meta)


@router.post("/sanctions/screen")
async def screen_subjects(body: ScreenBody) -> dict:
    cached_meta = _CACHE.get("meta")
    cache_mode = getattr(cached_meta, "mode", None) if cached_meta is not None else None
    need_load = "entries" not in _CACHE or "meta" not in _CACHE
    if body.prefer_live and cache_mode != "live":
        need_load = True
    if need_load:
        entries, meta = await load_dataset(prefer_live=body.prefer_live)
        _CACHE["entries"] = entries
        _CACHE["meta"] = meta
    else:
        entries = _CACHE["entries"]
        meta = _CACHE["meta"]

    matches = []
    for subject in body.subjects:
        for m in match_subject(subject, entries):
            matches.append(
                {
                    "subject": m.subject,
                    "matched_name": m.matched_name,
                    "list_uid": m.list_uid,
                    "score": m.score,
                    "band": m.band,
                    "programs": m.programs,
                    "review_status": "needs_review",
                    "disclaimer": m.disclaimer,
                }
            )
    return {
        "dataset": dataset_status(meta),
        "potential_matches": matches,
        "auto_sanctioned": False,
        "copy": "Potential match: requires human review",
    }


@router.post("/sanctions/assert-host")
async def assert_host(url: str = Query(...)) -> dict:
    """D3-02 helper: refuse non-treas.gov hosts."""
    try:
        assert_treas_gov_url(url)
        return {"ok": True, "url": url}
    except OfacHostRefused as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
