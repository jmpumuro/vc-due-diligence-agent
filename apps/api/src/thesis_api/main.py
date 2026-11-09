from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from thesis_api.db.session import SessionLocal
from thesis_api.routes import (
    assessments,
    auth,
    claims,
    dataroom,
    health,
    progress,
    review,
    screening,
    sanctions,
    system,
    ui_data,
)
from thesis_api.services.setup import ensure_setup_token, is_setup_complete
from thesis_api.settings import settings

logger = logging.getLogger("thesis_api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with SessionLocal() as session:
        try:
            if not await is_setup_complete(session):
                raw = await ensure_setup_token(session)
                if raw:
                    logger.warning(
                        "SETUP REQUIRED — one-time token (expires 24h): %s",
                        raw,
                    )
                else:
                    logger.warning(
                        "SETUP REQUIRED — token already issued this cycle; check earlier logs or recreate volumes"
                    )
        except Exception:  # noqa: BLE001 — DB may not be migrated yet at import in some jobs
            logger.exception("startup setup-token check failed")
    yield


app = FastAPI(title="Thesis API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.public_web_url, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(system.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(assessments.router, prefix="/api/v1")
app.include_router(claims.router, prefix="/api/v1")
app.include_router(progress.router, prefix="/api/v1")
app.include_router(review.router, prefix="/api/v1")
app.include_router(dataroom.router, prefix="/api/v1")
app.include_router(screening.router, prefix="/api/v1")
app.include_router(sanctions.router, prefix="/api/v1")
app.include_router(ui_data.router, prefix="/api/v1")


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "thesis-api", "docs": "/docs"}
