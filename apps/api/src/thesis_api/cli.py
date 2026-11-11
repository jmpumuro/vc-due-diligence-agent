"""One-shot container entrypoints: migrate and seed-demo."""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy.ext.asyncio import AsyncSession

from thesis_api.db.session import SessionLocal, engine
from thesis_api.services.seed_demo import DEMO_FIRM, purge_research_data, seed_demo


async def _seed(reset: bool) -> int:
    async with SessionLocal() as session:  # type: AsyncSession
        result = await seed_demo(session, reset=reset)
        print(result)
    await engine.dispose()
    return 0


async def _purge(*, firm_id: str | None) -> int:
    async with SessionLocal() as session:  # type: AsyncSession
        deleted = await purge_research_data(session, firm_id=firm_id)
        print({"status": "purged", "firm_id": firm_id or "*", "deleted": deleted})
    await engine.dispose()
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="thesis-api")
    sub = parser.add_subparsers(dest="cmd", required=True)
    seed_p = sub.add_parser("seed-demo")
    seed_p.add_argument("--reset", action="store_true")
    sub.add_parser("reap-sandboxes", help="Terminate expired sandboxes owned by this deployment.")
    purge_p = sub.add_parser(
        "purge-research",
        help="Delete assessments/claims/evidence (keeps demo auth users).",
    )
    purge_p.add_argument(
        "--all-firms",
        action="store_true",
        help="Purge every firm (default: frm_demo only).",
    )
    args = parser.parse_args(argv)
    if args.cmd == "seed-demo":
        return asyncio.run(_seed(args.reset))
    if args.cmd == "reap-sandboxes":
        from thesis_api.services.fetch.sandbox_reaper import reap_expired
        from thesis_api.settings import settings

        print({"expired_sandboxes_removed": asyncio.run(reap_expired(settings))})
        return 0
    if args.cmd == "purge-research":
        return asyncio.run(_purge(firm_id=None if args.all_firms else DEMO_FIRM))
    return 1


if __name__ == "__main__":
    sys.exit(main())
