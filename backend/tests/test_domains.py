"""Tests for the domain abstraction (Phase 1 foundation)."""

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

def test_default_domain_has_no_fixed_ontology():
    general = get_domain(DEFAULT_DOMAIN_KEY)
    assert general.key == "general"
    assert general.fixed_ontology is None
    assert general.uses_fixed_ontology is False


def test_empty_key_resolves_to_default():
    assert get_domain(None).key == DEFAULT_DOMAIN_KEY
    assert get_domain("").key == DEFAULT_DOMAIN_KEY


def test_oncology_domain_has_fixed_ontology():
    onc = get_domain("oncology_mdt")
    assert onc.uses_fixed_ontology is True
    assert onc.fixed_ontology is not None
    assert len(onc.fixed_ontology.entity_types) == 10
    names = {e.name for e in onc.fixed_ontology.entity_types}
    assert {"Patient", "CancerDiagnosis", "Specialist"}.issubset(names)
    # Patient and Specialist are the speaker-capable (individual) types.
    individuals = {e.name for e in onc.fixed_ontology.entity_types if e.is_individual}
    assert individuals == {"Patient", "Specialist"}
    # Every edge type references known entity types.
    for edge in onc.fixed_ontology.edge_types:
        for src, tgt in edge.source_targets:
            assert src in names and tgt in names


def test_oncology_domain_has_full_mdt_roster():
    onc = get_domain("oncology_mdt")
    assert onc.uses_fixed_roster is True
    roster = onc.fixed_agent_roster
    assert len(roster) == 10
    roles = {m.role for m in roster}
    assert {"Medical Oncologist", "Pathologist", "Patient Advocate"}.issubset(roles)
    for member in roster:
        assert member.role and member.persona and member.mandate


def test_build_roster_agents_is_deterministic():
    roster = get_domain("oncology_mdt").fixed_agent_roster
    agents = build_roster_agents(roster)
    assert len(agents) == len(roster)
    for agent, member in zip(agents, roster):
        assert agent.role == member.role
        assert agent.source_entity_type == "Specialist"
        assert agent.is_individual is True
        assert member.mandate in agent.persona  # mandate appended to persona


def test_unknown_domain_raises():
    try:
        get_domain("not_a_domain")
        assert False, "expected KeyError"
    except KeyError:
        pass
    assert is_valid_domain("not_a_domain") is False
    assert is_valid_domain("oncology_mdt") is True
    assert is_valid_domain(None) is True


def test_list_domains_is_default_first():
    domains = list_domains()
    assert domains[0].key == DEFAULT_DOMAIN_KEY
    assert {"general", "oncology_mdt", "quorum_dx_education"}.issubset(
        {d.key for d in domains}
    )


def test_dx_education_domain_full_shape():
    dx = get_domain("quorum_dx_education")
    assert dx.uses_fixed_ontology and dx.uses_fixed_roster and dx.uses_fixed_report
    assert len(dx.fixed_ontology.entity_types) == 10
    roles = {m.role for m in dx.fixed_agent_roster}
    # The reasoning archetypes that drive the debate.
    assert {"Generalist / Internist", "Skeptic", "Can't-Miss Agent", "Bayesian"}.issubset(roles)
    section_titles = [s.title for s in dx.fixed_report_outline]
    assert section_titles[0] == "Presentation summary"
    assert "Cognitive-bias flags" in section_titles


def test_dx_education_full_pipeline_emits_ddx_brief():
    test_dir = _make_test_dir()
    _reset_state(test_dir)
    try:
        with TestClient(main.app) as client:
            project_id = client.post(
                "/api/projects",
                json={
                    "brief": "55-year-old with sudden tearing back pain.",
                    "domain": "quorum_dx_education",
                    "title": "Case vignette",
                },
            ).json()["id"]
            for _ in range(7):
                r = client.post(
                    f"/api/projects/{project_id}/pipeline/run-next",
                    json={"rounds": 2, "agents_per_round": 3},
                )
                assert r.status_code == 200, r.text
            report = client.get(f"/api/projects/{project_id}").json()["report"]
            assert report["title"].startswith("Differential Diagnosis Brief")
            section_titles = [s["title"] for s in report["sections"]]
            assert section_titles[0] == "Presentation summary"
            assert section_titles[-1] == "Open questions and teaching points"
            assert "education only" in report["markdown"].lower()
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


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
            assert {"general", "oncology_mdt"}.issubset(keys)
            onc = next(d for d in domains if d["key"] == "oncology_mdt")
            assert onc["fixed_ontology"] is True
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_create_project_defaults_to_general_domain():
    test_dir = _make_test_dir()
    _reset_state(test_dir)
    try:
        with TestClient(main.app) as client:
            resp = client.post("/api/projects", json={"brief": "Should we ship feature X?"})
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


def test_oncology_project_uses_fixed_ontology():
    """Stage 01 applies the fixed oncology ontology verbatim, no LLM call."""
    test_dir = _make_test_dir()
    _reset_state(test_dir)
    try:
        with TestClient(main.app) as client:
            create_resp = client.post(
                "/api/projects",
                json={
                    "brief": "68-year-old with stage IIIA NSCLC, EGFR exon 19 deletion.",
                    "domain": "oncology_mdt",
                },
            )
            assert create_resp.status_code == 200
            project_id = create_resp.json()["id"]
            assert create_resp.json()["domain"] == "oncology_mdt"

            ontology_resp = client.post(
                f"/api/projects/{project_id}/graph/ontology/generate", json={}
            )
            assert ontology_resp.status_code == 200
            ontology = ontology_resp.json()["ontology"]
            entity_names = {e["name"] for e in ontology["entity_types"]}
            # The fixed schema, not an LLM-invented one.
            assert {"Patient", "CancerDiagnosis", "TumorStaging", "Specialist"}.issubset(
                entity_names
            )
            edge_names = {e["name"] for e in ontology["edge_types"]}
            assert "HAS_DIAGNOSIS" in edge_names
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_oncology_report_is_a_tumor_board_brief():
    """Stage 07 emits the fixed Tumor Board Brief shape, not the generic outline."""
    test_dir = _make_test_dir()
    _reset_state(test_dir)
    try:
        with TestClient(main.app) as client:
            project_id = client.post(
                "/api/projects",
                json={
                    "brief": "Newly diagnosed stage IIA case with HER2+ biomarker.",
                    "domain": "oncology_mdt",
                    "title": "HER2+ stage IIA case",
                },
            ).json()["id"]

            for _ in range(7):  # ontology -> graph -> env -> prepare -> activate -> sim -> report
                resp = client.post(
                    f"/api/projects/{project_id}/pipeline/run-next",
                    json={"rounds": 2, "agents_per_round": 3},
                )
                assert resp.status_code == 200, resp.text

            report = client.get(f"/api/projects/{project_id}").json()["report"]

            assert report["title"].startswith("Tumor Board Brief")
            assert "decision support" in report["summary"].lower()

            section_titles = [s["title"] for s in report["sections"]]
            assert section_titles == [
                "Case snapshot",
                "Recommended pathway",
                "Alternatives considered and why not",
                "Dissenting opinions",
                "Contraindications and safety flags",
                "Clinical trial eligibility",
                "Open questions for the human board",
            ]

            md = report["markdown"]
            assert "## Provenance" in md
            assert "Disclaimer" in md
            assert "decision support" in md.lower()
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)


def test_oncology_pipeline_convenes_fixed_panel_end_to_end():
    """The full specialized pipeline runs and convenes the 10-seat MDT panel."""
    test_dir = _make_test_dir()
    _reset_state(test_dir)
    try:
        with TestClient(main.app) as client:
            project_id = client.post(
                "/api/projects",
                json={
                    "brief": "72-year-old, stage IIA colon cancer, well-controlled diabetes.",
                    "domain": "oncology_mdt",
                },
            ).json()["id"]

            # Drive every stage through to the report.
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
            assert len(agents) == 10
            assert all(a["source_entity_type"] == "Specialist" for a in agents)
            assert "Medical Oncologist" in {a["role"] for a in agents}
            assert final["report"]["sections"]
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)
