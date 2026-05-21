"""Tests for the durable job queue (Phase 1 — job queue)."""

import os
import shutil
import tempfile
import time
from pathlib import Path

os.environ.setdefault("LLM_PROVIDER", "local")

from fastapi.testclient import TestClient

from quorum_backend import llm, main
from quorum_backend.pipeline import jobs as job_store
from quorum_backend.pipeline import router as pipeline_router


def _make_test_dir() -> Path:
    workspace_root = Path(__file__).resolve().parents[2]
    return Path(tempfile.mkdtemp(prefix="quorum-pipeline-test-", dir=str(workspace_root)))


def _reset_state(test_dir: Path):
    pipeline_router.clear_project_store_for_tests()
    llm._llm_provider = None


def _wait_for_job(client: TestClient, job_id: str, timeout: float = 15.0) -> dict:
    """Poll until the job is no longer pending/running, or raise."""
    deadline = time.time() + timeout
    last: dict = {}
    while time.time() < deadline:
        last = client.get(f"/api/jobs/{job_id}").json()
        if last["status"] in {"completed", "failed"}:
            return last
        time.sleep(0.2)
    raise AssertionError(f"Job {job_id} did not finish: {last}")


# --- Unit tests on the job store ----------------------------------------

def test_enqueue_and_get_round_trip():
    test_dir = _make_test_dir()
    _reset_state(test_dir)
    try:
        job = job_store.enqueue("proj_x", "run_next", {"rounds": 2})
        loaded = job_store.get(job.id)
        assert loaded is not None
        assert loaded.project_id == "proj_x"
        assert loaded.status == "pending"
        assert loaded.payload == {"rounds": 2}
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_claim_next_returns_oldest_pending_and_marks_running():
    test_dir = _make_test_dir()
    _reset_state(test_dir)
    try:
        a = job_store.enqueue("proj_x", "run_next")
        b = job_store.enqueue("proj_y", "run_next")
        claimed = job_store.claim_next()
        assert claimed is not None and claimed.id == a.id
        assert claimed.status == "running"
        # Second claim returns the other one.
        claimed_b = job_store.claim_next()
        assert claimed_b is not None and claimed_b.id == b.id
        # No more pending.
        assert job_store.claim_next() is None
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_mark_completed_and_failed_set_terminal_status():
    test_dir = _make_test_dir()
    _reset_state(test_dir)
    try:
        a = job_store.enqueue("p", "run_next")
        job_store.claim_next()
        job_store.mark_completed(a.id)
        assert job_store.get(a.id).status == "completed"

        b = job_store.enqueue("p", "run_next")
        job_store.claim_next()
        job_store.mark_failed(b.id, "boom")
        loaded = job_store.get(b.id)
        assert loaded.status == "failed"
        assert loaded.error == "boom"
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


# --- End-to-end: worker drives a real pipeline stage --------------------

def test_async_run_next_drives_one_stage_via_worker():
    test_dir = _make_test_dir()
    _reset_state(test_dir)
    try:
        with TestClient(main.app) as client:
            project_id = client.post(
                "/api/projects",
                json={"brief": "A general strategy question."},
            ).json()["id"]

            job = client.post(
                f"/api/projects/{project_id}/pipeline/run-async",
                json={"rounds": 2, "agents_per_round": 3},
            ).json()
            assert job["status"] == "pending"

            done = _wait_for_job(client, job["id"])
            assert done["status"] == "completed", done

            project = client.get(f"/api/projects/{project_id}").json()
            assert project["state"] == "ontology_generated"

            # The job shows up in the project's job list.
            project_jobs = client.get(f"/api/projects/{project_id}/jobs").json()["jobs"]
            assert any(j["id"] == job["id"] for j in project_jobs)
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_get_unknown_job_returns_404():
    test_dir = _make_test_dir()
    _reset_state(test_dir)
    try:
        with TestClient(main.app) as client:
            resp = client.get("/api/jobs/nope")
            assert resp.status_code == 404
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)
