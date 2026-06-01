import os
import shutil
import tempfile
from pathlib import Path

os.environ.setdefault("LLM_PROVIDER", "local")

from fastapi.testclient import TestClient

from quorum_backend import llm, main
from quorum_backend.pipeline import router as pipeline_router


def _make_test_dir() -> Path:
    workspace_root = Path(__file__).resolve().parents[2]
    return Path(
        tempfile.mkdtemp(
            prefix="quorum-pipeline-test-",
            dir=str(workspace_root),
        )
    )


def _reset_state(test_dir: Path):
    pipeline_router.clear_project_store_for_tests()
    llm._llm_provider = None


def test_pipeline_e2e_flow():
    test_dir = _make_test_dir()
    _reset_state(test_dir)

    try:
        with TestClient(main.app) as client:
            create_resp = client.post(
                "/api/projects",
                json={
                    "brief": "Should the team launch the new coordination workflow next quarter?",
                    "constraints": "Budget is fixed\nCompliance review cannot slip",
                    "signals": "Customer demand is rising",
                    # Pin to the general LLM-driven domain; this test asserts
                    # LLM-generated agent_configs / activation, which are
                    # intentionally skipped for fixed-roster domains.
                    "domain": "general",
                },
            )
            assert create_resp.status_code == 200
            created = create_resp.json()
            project_id = created["id"]

            upload_resp = client.post(
                f"/api/projects/{project_id}/upload",
                files={
                    "file": (
                        "seed.txt",
                        b"Stakeholders include regulators, the platform team, community advocates, and industry press.",
                        "text/plain",
                    )
                },
            )
            assert upload_resp.status_code == 200
            assert upload_resp.json()["uploaded_documents"][0]["filename"] == "seed.txt"

            pipeline_resp = client.get(f"/api/projects/{project_id}/pipeline")
            assert pipeline_resp.status_code == 200
            assert pipeline_resp.json()["current_step"] == "ontology"

            ontology_resp = client.post(f"/api/projects/{project_id}/graph/ontology/generate", json={})
            assert ontology_resp.status_code == 200
            ontology_project = ontology_resp.json()
            assert len(ontology_project["ontology"]["entity_types"]) == 10
            assert ontology_project["pipeline"]["current_step"] == "graph"

            graph_resp = client.post(f"/api/projects/{project_id}/graph/build", json={})
            assert graph_resp.status_code == 200
            graph_project = graph_resp.json()
            assert len(graph_project["graph"]["nodes"]) >= 12
            assert len(graph_project["graph"]["edges"]) >= 15

            env_resp = client.post(f"/api/projects/{project_id}/env/setup", json={})
            assert env_resp.status_code == 200
            env_project = env_resp.json()
            assert env_project["agent_count"] > 0
            first_agent_id = env_project["agents"][0]["id"]

            config_resp = client.post(f"/api/projects/{project_id}/simulation/prepare", json={})
            assert config_resp.status_code == 200
            config_project = config_resp.json()
            assert config_project["state"] == "config_ready"
            assert config_project["simulation_parameters"]["agent_configs"]
            assert config_project.get("activation") is None

            activation_resp = client.post(f"/api/projects/{project_id}/simulation/activate", json={})
            assert activation_resp.status_code == 200
            activation_project = activation_resp.json()
            assert activation_project["state"] == "activation_ready"
            assert activation_project["activation"]["initial_posts"]
            assert activation_project["activation"]["hot_topics"]

            simulation_resp = client.post(
                f"/api/projects/{project_id}/simulation/start",
                json={"rounds": 2, "agents_per_round": 3},
            )
            assert simulation_resp.status_code == 200
            simulation_project = simulation_resp.json()
            assert simulation_project["state"] == "sim_completed"
            assert simulation_project["consensus"] is not None
            assert any(message["round"] == 0 for message in simulation_project["debate_messages"])
            assert any(message["round"] == 1 for message in simulation_project["debate_messages"])

            report_resp = client.post(f"/api/projects/{project_id}/report/generate", json={})
            assert report_resp.status_code == 200
            report_project = report_resp.json()
            assert report_project["state"] == "report_ready"
            assert report_project["report"]["sections"]

            chat_resp = client.post(
                f"/api/projects/{project_id}/agents/{first_agent_id}/chat",
                json={"message": "What is the gating risk from your perspective?"},
            )
            assert chat_resp.status_code == 200
            assert "reply" in chat_resp.json()
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_pipeline_run_next_and_upload_guard():
    test_dir = _make_test_dir()
    _reset_state(test_dir)

    try:
        with TestClient(main.app) as client:
            create_resp = client.post(
                "/api/projects",
                json={
                    "brief": "Should we change the operating model for the service rollout?",
                    "domain": "general",
                },
            )
            assert create_resp.status_code == 200
            project_id = create_resp.json()["id"]

            expected_states = [
                "ontology_generated",
                "graph_completed",
                "env_ready",
                "config_ready",
                "activation_ready",
                "sim_completed",
                "report_ready",
            ]

            for expected in expected_states:
                next_resp = client.post(
                    f"/api/projects/{project_id}/pipeline/run-next",
                    json={"rounds": 2, "agents_per_round": 3},
                )
                assert next_resp.status_code == 200
                assert next_resp.json()["state"] == expected

            late_upload = client.post(
                f"/api/projects/{project_id}/upload",
                files={"file": ("late.txt", b"late context", "text/plain")},
            )
            assert late_upload.status_code == 409
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)
