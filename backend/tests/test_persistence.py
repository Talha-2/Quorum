"""Tests for the database-backed project store (Phase 1)."""

import os
import shutil
import tempfile
from pathlib import Path

os.environ.setdefault("LLM_PROVIDER", "local")

from fastapi.testclient import TestClient

from quorum_backend import llm, main
from quorum_backend.pipeline import db
from quorum_backend.pipeline import router as pipeline_router
from quorum_backend.pipeline.models import Project, ProjectState
from quorum_backend.pipeline.serialization import project_from_dict, project_to_dict


def _make_test_dir() -> Path:
    workspace_root = Path(__file__).resolve().parents[2]
    return Path(tempfile.mkdtemp(prefix="quorum-pipeline-test-", dir=str(workspace_root)))


def _reset_state(test_dir: Path):
    pipeline_router.clear_project_store_for_tests()
    llm._llm_provider = None


# --- Serialization round-trip -------------------------------------------

def test_project_dict_round_trip_preserves_fields():
    project = Project(id="proj_test", title="Round trip", brief="A brief")
    project.domain = "oncology_mdt"
    project.transition(ProjectState.ONTOLOGY_GENERATED, "ontology ready")

    restored = project_from_dict(project_to_dict(project))

    assert restored.id == project.id
    assert restored.title == project.title
    assert restored.brief == project.brief
    assert restored.domain == "oncology_mdt"
    assert restored.state == ProjectState.ONTOLOGY_GENERATED
    assert isinstance(restored.state, ProjectState)
    assert len(restored.events) == len(project.events)


# --- Database round-trip -------------------------------------------------

def test_save_and_load_project_through_database():
    test_dir = _make_test_dir()
    _reset_state(test_dir)
    try:
        project = Project(id="proj_db", title="DB project", brief="Persisted brief")
        db.save_project(project)

        loaded = db.load_all_projects()
        assert "proj_db" in loaded
        assert loaded["proj_db"].brief == "Persisted brief"

        # Upsert: saving again updates rather than duplicates.
        project.title = "Renamed"
        db.save_project(project)
        assert db.project_count() == 1
        assert db.load_all_projects()["proj_db"].title == "Renamed"
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_project_survives_a_simulated_restart():
    """A project written through the API is recoverable after a cache reload."""
    test_dir = _make_test_dir()
    _reset_state(test_dir)
    try:
        with TestClient(main.app) as client:
            project_id = client.post(
                "/api/projects",
                json={
                    "brief": "Stage IIA case for review.",
                    "domain": "oncology_mdt",
                },
            ).json()["id"]
            client.post(f"/api/projects/{project_id}/graph/ontology/generate", json={})
            client.post(f"/api/projects/{project_id}/graph/build", json={})
            client.post(f"/api/projects/{project_id}/env/setup", json={})

        # Simulate a process restart: drop the in-memory cache, reload from DB.
        pipeline_router._projects = {}
        pipeline_router.load_projects_into_cache()

        with TestClient(main.app) as client:
            resp = client.get(f"/api/projects/{project_id}")
            assert resp.status_code == 200
            recovered = resp.json()
            assert recovered["domain"] == "oncology_mdt"
            assert recovered["ontology"] is not None
            assert recovered["agent_count"] == 10
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)
