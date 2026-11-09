"""Ensure frm_demo auth shell exists. Does not load fixture mock companies."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from thesis_api.db.models import AppUser, Firm, SeedMarker

# Errata E4: fixture firm id remapped to frm_demo at seed time.
DEMO_FIRM = "frm_demo"

_RESEARCH_TABLES = (
    "contradiction_resolution_events",
    "contradictions",
    "evidence_spans",
    "evidence_snapshots",
    "claims",
    "domain_progress_events",
    "review_decisions",
    "review_targets",
    "documents",
    "data_rooms",
    "deal_team_members",
    "budget_reservations",
    "notifications",
    "outbox_events",
    "retention_records",
    "external_operations",
    "watchlist_entries",
    "assessments",
)


async def _table_has_column(session: AsyncSession, table: str, column: str) -> bool:
    row = (
        await session.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name=:t AND column_name=:c"
            ),
            {"t": table, "c": column},
        )
    ).first()
    return row is not None


async def purge_research_data(session: AsyncSession, *, firm_id: str | None = None) -> dict:
    """Delete assessments and research artifacts. Keeps firms/users for auth."""
    deleted: dict[str, int] = {}
    for table in _RESEARCH_TABLES:
        if firm_id:
            if await _table_has_column(session, table, "firm_id"):
                result = await session.execute(
                    text(f"DELETE FROM {table} WHERE firm_id = :f"), {"f": firm_id}
                )
            elif await _table_has_column(session, table, "assessment_id"):
                result = await session.execute(
                    text(
                        f"DELETE FROM {table} WHERE assessment_id IN "
                        f"(SELECT id FROM assessments WHERE firm_id = :f)"
                    ),
                    {"f": firm_id},
                )
            else:
                continue
        else:
            result = await session.execute(text(f"DELETE FROM {table}"))
        deleted[table] = result.rowcount or 0
    sess = await session.execute(text("DELETE FROM sessions"))
    deleted["sessions"] = sess.rowcount or 0
    await session.commit()
    return deleted


async def seed_demo(session: AsyncSession, *, reset: bool = False) -> dict:
    """Ensure one firm + one partner user. No fixture mock assessments."""
    existing = (
        await session.execute(select(SeedMarker).where(SeedMarker.name == "demo_workspace"))
    ).scalar_one_or_none()
    if existing and not reset:
        # Keep workspace lean: one partner only (drop extra seeded users).
        await session.execute(
            text(
                "DELETE FROM users WHERE firm_id = :f AND email <> :email"
            ),
            {"f": DEMO_FIRM, "email": "demo@thesis.local"},
        )
        await session.commit()
        user = (
            await session.execute(select(AppUser).where(AppUser.email == "demo@thesis.local"))
        ).scalar_one_or_none()
        return {
            "status": "already_seeded",
            "firm_id": DEMO_FIRM,
            "user_id": user.id if user else None,
            "email": "demo@thesis.local",
            "assessments": [],
            "fixture_assessments": False,
        }

    if reset:
        await purge_research_data(session, firm_id=DEMO_FIRM)
        await session.execute(text("DELETE FROM users WHERE firm_id = :f"), {"f": DEMO_FIRM})
        await session.execute(text("DELETE FROM firms WHERE id = :f"), {"f": DEMO_FIRM})
        await session.execute(text("DELETE FROM seed_markers WHERE name = 'demo_workspace'"))
        await session.commit()

    if (await session.execute(select(Firm).where(Firm.id == DEMO_FIRM))).scalar_one_or_none() is None:
        session.add(Firm(id=DEMO_FIRM, name="Thesis"))

    user = (
        await session.execute(select(AppUser).where(AppUser.email == "demo@thesis.local"))
    ).scalar_one_or_none()
    if user is None:
        user = AppUser(
            id=str(uuid4()),
            email="demo@thesis.local",
            display_name="Partner",
            firm_id=DEMO_FIRM,
            roles=["partner"],
            is_demo=True,
        )
        session.add(user)

    # Exactly one user on the firm.
    await session.execute(
        text("DELETE FROM users WHERE firm_id = :f AND email <> :email"),
        {"f": DEMO_FIRM, "email": "demo@thesis.local"},
    )

    if (
        await session.execute(select(SeedMarker).where(SeedMarker.name == "demo_workspace"))
    ).scalar_one_or_none() is None:
        session.add(
            SeedMarker(
                name="demo_workspace",
                detail="One firm + one partner; no fixture mock assessments.",
            )
        )
    await session.commit()
    return {
        "status": "seeded",
        "firm_id": DEMO_FIRM,
        "user_id": user.id,
        "email": user.email,
        "assessments": [],
        "fixture_assessments": False,
    }
