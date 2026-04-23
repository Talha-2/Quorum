import os

os.environ.setdefault("LLM_PROVIDER", "local")

from fastapi.testclient import TestClient

from backend import llm, main


def test_execution_domain_e2e_flow():
    """End-to-end happy path covering initialize -> simulate -> chat -> history."""
    # ensure deterministic provider each test run
    llm._llm_provider = None

    with TestClient(main.app) as client:
        init_resp = client.post("/initialize/execution", json={})
        assert init_resp.status_code == 200
        init_data = init_resp.json()

        sim_id = init_data["simulation_id"]
        assert init_data["status"] == "ready"
        assert len(init_data["agents"]) >= 4

        scenario_payload = {
            "domain": "execution",
            "scenario_description": "Backend slips by two weeks",
            "scenario_changes": {"backend_delay_days": 14},
        }
        sim_resp = client.post("/simulate", json=scenario_payload)
        assert sim_resp.status_code == 200
        sim_data = sim_resp.json()

        assert sim_data["result"]["consensus"] is not None
        assert len(sim_data["result"]["agent_predictions"]) == len(init_data["agents"])

        chat_payload = {
            "simulation_id": sim_id,
            "message": "What should we prioritize to stay on schedule?",
            "get_consensus": True,
        }
        chat_resp = client.post(f"/chat/{sim_id}", json=chat_payload)
        assert chat_resp.status_code == 200
        chat_data = chat_resp.json()

        assert chat_data["responses"], "Agents should respond"
        assert chat_data["consensus"], "Consensus text expected when requested"

        history_resp = client.get(f"/simulation/{sim_id}/history")
        assert history_resp.status_code == 200
        history_data = history_resp.json()

        assert history_data["simulations_run"] >= 1
        assert any(
            entry["scenario"]["description"] == scenario_payload["scenario_description"]
            for entry in history_data["history"]
        )

