"""
Database layer for the project store.

A project is an aggregate persisted as one row with a JSON ``data`` column;
a few fields are also stored as columns for indexing and quick listing.
PostgreSQL is the production target; an unset ``DATABASE_URL`` falls back to
a local SQLite file so the app runs with zero configuration.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

from sqlalchemy import (
    Column,
    MetaData,
    String,
    Table,
    create_engine,
    delete,
    func,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.types import JSON

from quorum_backend.config import settings
from quorum_backend.pipeline.models import Project
from quorum_backend.pipeline.serialization import project_from_dict, project_to_dict

logger = logging.getLogger(__name__)

metadata = MetaData()

# The project store. ``data`` holds the full serialized aggregate; the other
# columns are projections of it kept for indexing and listing.
projects_table = Table(
    "projects",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("domain", String(64), nullable=False, server_default="general"),
    Column("state", String(32), nullable=False),
    Column("title", String(512), nullable=False, server_default=""),
    Column("created_at", String(64), nullable=False),
    Column("updated_at", String(64), nullable=False),
    Column("data", JSON, nullable=False),
)

_engine: Optional[Engine] = None


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def get_engine() -> Engine:
    """Return the process-wide SQLAlchemy engine, creating it on first use."""
    global _engine
    if _engine is None:
        url = settings.resolved_database_url
        connect_args = {"check_same_thread": False} if _is_sqlite(url) else {}
        _engine = create_engine(
            url,
            future=True,
            pool_pre_ping=True,
            connect_args=connect_args,
        )
        # Log the URL without credentials.
        safe = url.split("@")[-1] if "@" in url else url
        logger.info("Database engine created (%s)", safe)
    return _engine


def reset_engine_for_tests() -> None:
    """Drop the cached engine so a test can point at a different database."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None


def _migrations_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "migrations"


def init_db() -> None:
    """Bring the schema up to date by running Alembic migrations to head."""
    from alembic import command
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(_migrations_dir()))
    cfg.set_main_option("sqlalchemy.url", settings.resolved_database_url)
    command.upgrade(cfg, "head")
    logger.info("Database schema is at head revision")


def load_all_projects() -> Dict[str, Project]:
    """Load every project into a dict keyed by id."""
    engine = get_engine()
    projects: Dict[str, Project] = {}
    with engine.connect() as conn:
        for (payload,) in conn.execute(select(projects_table.c.data)):
            try:
                project = project_from_dict(payload)
                projects[project.id] = project
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Skipping unreadable project row: %s", exc)
    logger.info("Loaded %d project(s) from the database", len(projects))
    return projects


def save_project(project: Project) -> None:
    """Insert or update a single project (upsert)."""
    engine = get_engine()
    values = {
        "id": project.id,
        "domain": getattr(project, "domain", "general"),
        "state": project.state.value,
        "title": project.title,
        "created_at": project.created_at,
        "updated_at": project.updated_at,
        "data": project_to_dict(project),
    }
    with engine.begin() as conn:
        exists = conn.execute(
            select(projects_table.c.id).where(projects_table.c.id == project.id)
        ).first()
        if exists:
            conn.execute(
                projects_table.update()
                .where(projects_table.c.id == project.id)
                .values(**values)
            )
        else:
            conn.execute(projects_table.insert().values(**values))


def clear_all_projects() -> None:
    """Delete every project row. Used by tests."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(delete(projects_table))


def project_count() -> int:
    engine = get_engine()
    with engine.connect() as conn:
        return int(
            conn.execute(select(func.count()).select_from(projects_table)).scalar() or 0
        )
