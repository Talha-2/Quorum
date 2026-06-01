"""
Single-process async worker that drains the pipeline job queue.

The worker is started by :func:`start_worker` from the FastAPI lifespan
and runs as one ``asyncio.Task`` for the lifetime of the process. It
polls the ``jobs`` table for pending work and executes each job against
the in-memory project store, serially. Long-running stages don't block
request threads because the worker runs in its own task.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from quorum_backend.pipeline import jobs as job_store
from quorum_backend.pipeline.jobs import Job

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 0.5  # used in production
_worker_task: Optional[asyncio.Task] = None
_stop_event: Optional[asyncio.Event] = None


async def _execute(job: Job) -> None:
    """Run one job. Importing the router here breaks an import cycle."""
    from quorum_backend.pipeline import router as pipeline_router
    from quorum_backend.pipeline.router import RunNextStageRequest

    project = pipeline_router._projects.get(job.project_id)
    if project is None:
        # Cache miss can happen when the project was created in a different
        # asyncio task/thread (e.g. the TestClient request thread) and the
        # write isn't yet visible to the worker. Fall back to loading from
        # the DB and warming the cache before giving up.
        logger.info(
            "Job %s: project %s not in cache, reloading from DB",
            job.id,
            job.project_id,
        )
        from quorum_backend.pipeline import db as db_module

        all_projects = db_module.load_all_projects()
        if job.project_id in all_projects:
            pipeline_router._projects[job.project_id] = all_projects[job.project_id]
            project = all_projects[job.project_id]
        else:
            raise RuntimeError(f"Project {job.project_id} not found in cache or DB")

    async with pipeline_router._get_project_lock(job.project_id):
        if job.job_type == "run_next":
            rounds = int(job.payload.get("rounds", 3))
            agents_per_round = int(job.payload.get("agents_per_round", 4))
            next_stage = pipeline_router._next_stage_id(project)
            if next_stage is None:
                return  # nothing to do
            if next_stage == "ontology":
                await pipeline_router._run_ontology_stage(project)
            elif next_stage == "graph":
                await pipeline_router._run_graph_stage(project)
            elif next_stage == "env":
                await pipeline_router._run_env_stage(project)
            elif next_stage == "prepare":
                await pipeline_router._run_prepare_stage(project)
            elif next_stage == "activate":
                await pipeline_router._run_activation_stage(project)
            elif next_stage == "simulate":
                await pipeline_router._run_simulation_stage(
                    project, RunNextStageRequest(rounds=rounds, agents_per_round=agents_per_round)
                )
            elif next_stage == "report":
                await pipeline_router._run_report_stage(project)
            else:
                raise RuntimeError(f"Unknown next stage: {next_stage}")
            pipeline_router._save_project(project)
        else:
            raise RuntimeError(f"Unknown job type: {job.job_type}")


async def _worker_loop(stop_event: asyncio.Event, poll_interval: float) -> None:
    logger.info("Job worker started (poll_interval=%.1fs)", poll_interval)
    while not stop_event.is_set():
        try:
            job = await asyncio.to_thread(job_store.claim_next)
            if job is None:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=poll_interval)
                except asyncio.TimeoutError:
                    pass
                continue
            try:
                await _execute(job)
                await asyncio.to_thread(job_store.mark_completed, job.id)
            except Exception as exc:
                logger.exception("Job %s failed", job.id)
                await asyncio.to_thread(job_store.mark_failed, job.id, str(exc))
        except Exception:
            # Never let the worker die on an unexpected error.
            logger.exception("Job worker iteration failed")
            await asyncio.sleep(poll_interval)
    logger.info("Job worker stopped")


def start_worker(poll_interval: float = POLL_INTERVAL_SECONDS) -> None:
    """Start the worker if it is not already running. Idempotent."""
    global _worker_task, _stop_event
    if _worker_task is not None and not _worker_task.done():
        return
    _stop_event = asyncio.Event()
    _worker_task = asyncio.create_task(_worker_loop(_stop_event, poll_interval))


async def stop_worker() -> None:
    """Signal the worker to exit and wait for it. Idempotent."""
    global _worker_task, _stop_event
    if _stop_event is not None:
        _stop_event.set()
    if _worker_task is not None:
        try:
            await asyncio.wait_for(_worker_task, timeout=5.0)
        except asyncio.TimeoutError:
            _worker_task.cancel()
        _worker_task = None
        _stop_event = None
