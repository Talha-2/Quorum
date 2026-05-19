"""
Application entrypoint for the Quorum backend.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from quorum_backend.config import settings
from quorum_backend.llm import get_llm, init_llm
from quorum_backend.observability import configure_logging
from quorum_backend.pipeline import db
from quorum_backend.pipeline.router import (
    get_project_store_summary,
    load_projects_into_cache,
    router as pipeline_router,
)

configure_logging(settings.log_format)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    init_llm()
    # Bring the database schema to head, then warm the in-memory cache.
    db.init_db()
    load_projects_into_cache()
    yield


app = FastAPI(
    title=settings.app_name,
    description="Quorum — multi-agent reasoning platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pipeline_router)


@app.get("/health")
async def health():
    llm = get_llm()
    store = get_project_store_summary()
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": "1.0.0",
        "llm_provider_configured": settings.llm_provider,
        "llm_provider_active": getattr(llm, "name", "unknown"),
        "llm_provider_ok": getattr(llm, "name", "unknown") == settings.llm_provider,
        "project_count": store["project_count"],
        "project_store": store["store_path"],
    }

