"""Tests for the domain abstraction and the engineering_rfc domain."""

import os
import shutil
import tempfile
from pathlib import Path

os.environ.setdefault("LLM_PROVIDER", "local")

from fastapi.testclient import TestClient

from quorum_backend import llm, main
from quorum_backend.domains import DEFAULT_DOMAIN_KEY, get_domain, is_valid_domain, list_domains
from quorum_backend.pipeline import router as pipeline_router
from quorum_backend.pipeline.env_setup import build_roster_agents


def _make_test_dir() -> Path:
    workspace_root = Path(__file__).resolve().parents[2]
    return Path(tempfile.mkdtemp(prefix="quorum-pipeline-test-", dir=str(workspace_root)))


def _reset_state(test_dir: Path):
    pipeline_router.clear_project_store_for_tests()
    llm._llm_provider = None


# --- Registry unit tests -------------------------------------------------

def test_default_domain_is_engineering_rfc():
    default = get_domain(DEFAULT_DOMAIN_KEY)
    assert default.key == "engineering_rfc"
    assert default.uses_fixed_ontology is True
    assert default.uses_fixed_roster is True


def test_general_domain_still_available_as_fallback():
    general = get_domain("general")
    assert general.fixed_ontology is None
    assert general.uses_fixed_ontology is False


def test_empty_key_resolves_to_default():
    assert get_domain(None).key == DEFAULT_DOMAIN_KEY
    assert get_domain("").key == DEFAULT_DOMAIN_KEY


def test_engineering_rfc_domain_has_fixed_ontology():
    rfc = get_domain("engineering_rfc")
    assert rfc.uses_fixed_ontology is True
    assert rfc.fixed_ontology is not None
    assert len(rfc.fixed_ontology.entity_types) == 10
    names = {e.name for e in rfc.fixed_ontology.entity_types}
    assert {"Decision", "Alternative", "Tradeoff", "Reviewer"}.issubset(names)
    # Reviewer is the only speaker-capable (individual) entity.
    individuals = {e.name for e in rfc.fixed_ontology.entity_types if e.is_individual}
    assert individuals == {"Reviewer"}
    # Every edge type references known entity types.
    for edge in rfc.fixed_ontology.edge_types:
        for src, tgt in edge.source_targets:
            assert src in names and tgt in names


def test_engineering_rfc_domain_has_reviewer_roster():
    rfc = get_domain("engineering_rfc")
    assert rfc.uses_fixed_roster is True
    roster = rfc.fixed_agent_roster
    assert len(roster) == 7
    roles = {m.role for m in roster}
    assert {
        "Principal Engineer",
        "Reliability Engineer",
        "Security Engineer",
        "Skeptic",
    }.issubset(roles)
    for member in roster:
        assert member.role and member.persona and member.mandate


def test_build_roster_agents_is_deterministic():
    roster = get_domain("engineering_rfc").fixed_agent_roster
    agents = build_roster_agents(roster)
    assert len(agents) == len(roster)
    for agent, member in zip(agents, roster):
        assert agent.role == member.role
        assert agent.source_entity_type == "Specialist"
        assert agent.is_individual is True
        assert member.mandate in agent.persona  # mandate appended to persona


def test_engineering_rfc_domain_full_shape():
    rfc = get_domain("engineering_rfc")
    assert rfc.uses_fixed_ontology and rfc.uses_fixed_roster and rfc.uses_fixed_report
    section_titles = [s.title for s in rfc.fixed_report_outline]
    assert section_titles[0] == "Context"
    assert "Why not the alternatives" in section_titles
    assert section_titles[-1] == "Follow-ups and open questions"


def test_unknown_domain_raises():
    try:
        get_domain("not_a_domain")
        assert False, "expected KeyError"
    except KeyError:
        pass
    assert is_valid_domain("not_a_domain") is False
    assert is_valid_domain("engineering_rfc") is True
    assert is_valid_domain(None) is True


def test_list_domains_is_default_first():
    domains = list_domains()
    assert domains[0].key == DEFAULT_DOMAIN_KEY
    assert domains[0].key == "engineering_rfc"
    assert {"general", "engineering_rfc"}.issubset({d.key for d in domains})


# --- API integration tests ----------------------------------------------

def test_domains_endpoint():
    test_dir = _make_test_dir()
    _reset_state(test_dir)
    try:
        with TestClient(main.app) as client:
            resp = client.get("/api/domains")
            assert resp.status_code == 200
            domains = resp.json()["domains"]
            keys = {d["key"] for d in domains}
            assert {"general", "engineering_rfc"}.issubset(keys)
            rfc = next(d for d in domains if d["key"] == "engineering_rfc")
            assert rfc["fixed_ontology"] is True
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_create_project_defaults_to_engineering_rfc_domain():
    test_dir = _make_test_dir()
    _reset_state(test_dir)
    try:
        with TestClient(main.app) as client:
            resp = client.post(
                "/api/projects",
                json={"brief": "Adopt PostgreSQL over MongoDB for the orders service."},
            )
            assert resp.status_code == 200
            assert resp.json()["domain"] == "engineering_rfc"
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_create_project_can_still_opt_into_general():
    test_dir = _make_test_dir()
    _reset_state(test_dir)
    try:
        with TestClient(main.app) as client:
            resp = client.post(
                "/api/projects",
                json={"brief": "Strategy brief", "domain": "general"},
            )
            assert resp.status_code == 200
            assert resp.json()["domain"] == "general"
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_create_project_with_unknown_domain_is_rejected():
    test_dir = _make_test_dir()
    _reset_state(test_dir)
    try:
        with TestClient(main.app) as client:
            resp = client.post(
                "/api/projects",
                json={"brief": "A brief", "domain": "bogus_domain"},
            )
            assert resp.status_code == 400
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_engineering_rfc_project_uses_fixed_ontology():
    """Stage 01 applies the fixed engineering RFC ontology verbatim, no LLM call."""
    test_dir = _make_test_dir()
    _reset_state(test_dir)
    try:
        with TestClient(main.app) as client:
            create_resp = client.post(
                "/api/projects",
                json={
                    "brief": "Adopt PostgreSQL over MongoDB for the orders service.",
                    "domain": "engineering_rfc",
                },
            )
            assert create_resp.status_code == 200
            project_id = create_resp.json()["id"]
            assert create_resp.json()["domain"] == "engineering_rfc"

            ontology_resp = client.post(
                f"/api/projects/{project_id}/graph/ontology/generate", json={}
            )
            assert ontology_resp.status_code == 200
            ontology = ontology_resp.json()["ontology"]
            entity_names = {e["name"] for e in ontology["entity_types"]}
            assert {"Decision", "Alternative", "Tradeoff", "Reviewer"}.issubset(entity_names)
            edge_names = {e["name"] for e in ontology["edge_types"]}
            assert "CONSIDERS" in edge_names and "INVOLVES_TRADEOFF" in edge_names
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_engineering_rfc_report_is_an_adr():
    """Stage 07 emits the fixed ADR shape, not the generic outline."""
    test_dir = _make_test_dir()
    _reset_state(test_dir)
    try:
        with TestClient(main.app) as client:
            project_id = client.post(
                "/api/projects",
                json={
                    "brief": "Carve the billing path out of the monolith.",
                    "domain": "engineering_rfc",
                    "title": "Billing service extraction",
                },
            ).json()["id"]

            for _ in range(7):  # ontology -> graph -> env -> prepare -> activate -> sim -> report
                resp = client.post(
                    f"/api/projects/{project_id}/pipeline/run-next",
                    json={"rounds": 2, "agents_per_round": 3},
                )
                assert resp.status_code == 200, resp.text

            report = client.get(f"/api/projects/{project_id}").json()["report"]

            assert report["title"].startswith("ADR")
            assert "decision support" in report["summary"].lower()

            section_titles = [s["title"] for s in report["sections"]]
            assert section_titles == [
                "Context",
                "Decision drivers",
                "Alternatives considered",
                "Recommended decision",
                "Why not the alternatives",
                "Dissents",
                "Consequences and risks",
                "Follow-ups and open questions",
            ]

            md = report["markdown"]
            assert "## Provenance" in md
            assert "Disclaimer" in md
            assert "engineering team owns" in md.lower()
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_engineering_rfc_pipeline_convenes_fixed_panel_end_to_end():
    """The full specialized pipeline runs and convenes the 7-seat reviewer panel."""
    test_dir = _make_test_dir()
    _reset_state(test_dir)
    try:
        with TestClient(main.app) as client:
            project_id = client.post(
                "/api/projects",
                json={
                    "brief": "Pick the next observability stack.",
                    "domain": "engineering_rfc",
                },
            ).json()["id"]

            for expected in [
                "ontology_generated",
                "graph_completed",
                "env_ready",
                "config_ready",
                "activation_ready",
                "sim_completed",
                "report_ready",
            ]:
                resp = client.post(
                    f"/api/projects/{project_id}/pipeline/run-next",
                    json={"rounds": 2, "agents_per_round": 3},
                )
                assert resp.status_code == 200, resp.text
                assert resp.json()["state"] == expected

            final = client.get(f"/api/projects/{project_id}").json()
            agents = final["agents"]
            assert len(agents) == 7
            assert all(a["source_entity_type"] == "Specialist" for a in agents)
            assert "Principal Engineer" in {a["role"] for a in agents}
            assert final["report"]["sections"]
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)
