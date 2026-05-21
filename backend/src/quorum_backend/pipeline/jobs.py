"""
Durable, Postgres-backed pipeline job queue.

A job represents one pending unit of pipeline work for a project (today:
``run_next``, which advances the project by one stage). Jobs are stored in
SQL so they survive process restarts, and a single in-process worker
(see :mod:`quorum_backend.pipeline.worker`) executes them serially.

Design intent: this is purely additive — the existing synchronous stage
endpoints are unchanged. New async endpoints (``/pipeline/run-async``,
``/jobs/{id}``) enqueue jobs and report status, so a client that wants
durable, restart-safe pipeline runs can use them. The frontend continues
to work via the sync path.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, MetaData, String, Table, select
from sqlalchemy.types import JSON

from quorum_backend.pipeline.db import get_engine, metadata as _db_metadata
from quorum_backend.pipeline.models import utc_now_iso

logger = logging.getLogger(__name__)


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    id: str
    project_id: str
    job_type: str
    status: str
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Share the project store's metadata so Alembic sees both tables.
jobs_table = Table(
    "jobs",
    _db_metadata,
    Column("id", String(64), primary_key=True),
    Column("project_id", String(64), nullable=False, index=True),
    Column("job_type", String(32), nullable=False),
    Column("status", String(16), nullable=False, index=True),
    Column("payload", JSON, nullable=False),
    Column("created_at", String(64), nullable=False),
    Column("started_at", String(64), nullable=True),
    Column("completed_at", String(64), nullable=True),
    Column("error", String, nullable=True),
)


def _row_to_job(row: Any) -> Job:
    return Job(
        id=row.id,
        project_id=row.project_id,
        job_type=row.job_type,
        status=row.status,
        payload=row.payload or {},
        created_at=row.created_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
        error=row.error,
    )


def make_job_id() -> str:
    return f"job_{uuid.uuid4().hex[:12]}"


def enqueue(project_id: str, job_type: str, payload: Optional[Dict[str, Any]] = None) -> Job:
    """Insert a new pending job. Returns the persisted record."""
    job = Job(
        id=make_job_id(),
        project_id=project_id,
        job_type=job_type,
        status=JobStatus.PENDING.value,
        payload=payload or {},
        created_at=utc_now_iso(),
    )
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(jobs_table.insert().values(**job.to_dict()))
    logger.info("Enqueued job %s (%s) for project %s", job.id, job_type, project_id)
    return job


def get(job_id: str) -> Optional[Job]:
    engine = get_engine()
    with engine.connect() as conn:
        row = conn.execute(
            select(jobs_table).where(jobs_table.c.id == job_id)
        ).first()
    return _row_to_job(row) if row else None


def list_for_project(project_id: str, limit: int = 20) -> List[Job]:
    engine = get_engine()
    with engine.connect() as conn:
        rows = conn.execute(
            select(jobs_table)
            .where(jobs_table.c.project_id == project_id)
            .order_by(jobs_table.c.created_at.desc())
            .limit(limit)
        ).all()
    return [_row_to_job(r) for r in rows]


def claim_next() -> Optional[Job]:
    """Claim the oldest pending job and mark it running.

    Atomic per row: SELECT + UPDATE inside a single transaction. On Postgres
    this is wrapped with ``FOR UPDATE SKIP LOCKED`` so multiple workers
    don't fight (today there is only one). SQLite ignores the lock hint —
    it serializes writers by default, which is fine for dev.
    """
    engine = get_engine()
    dialect = engine.dialect.name
    with engine.begin() as conn:
        stmt = (
            select(jobs_table)
            .where(jobs_table.c.status == JobStatus.PENDING.value)
            .order_by(jobs_table.c.created_at)
            .limit(1)
        )
        if dialect == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)
        row = conn.execute(stmt).first()
        if row is None:
            return None
        now = utc_now_iso()
        conn.execute(
            jobs_table.update()
            .where(jobs_table.c.id == row.id)
            .values(status=JobStatus.RUNNING.value, started_at=now)
        )
        return Job(
            id=row.id,
            project_id=row.project_id,
            job_type=row.job_type,
            status=JobStatus.RUNNING.value,
            payload=row.payload or {},
            created_at=row.created_at,
            started_at=now,
            completed_at=None,
            error=None,
        )


def mark_completed(job_id: str) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            jobs_table.update()
            .where(jobs_table.c.id == job_id)
            .values(status=JobStatus.COMPLETED.value, completed_at=utc_now_iso())
        )


def mark_failed(job_id: str, error: str) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            jobs_table.update()
            .where(jobs_table.c.id == job_id)
            .values(
                status=JobStatus.FAILED.value,
                completed_at=utc_now_iso(),
                error=error[:8000],
            )
        )


def clear_all_jobs_for_tests() -> None:
    """Wipe the jobs table. Used by tests."""
    engine = get_engine()
    from sqlalchemy import delete

    with engine.begin() as conn:
        conn.execute(delete(jobs_table))
