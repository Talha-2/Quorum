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


def _make_test_dir() -> Path:
    workspace_root = Path(__file__).resolve().parents[2]
    return Path(tempfile.mkdtemp(prefix="quorum-pipeline-test-", dir=str(workspace_root)))


def _reset_state(test_dir: Path):
    pipeline_router._PROJECT_STORE_PATH = test_dir / "projects.pkl"
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
    assert {"general", "oncology_mdt"}.issubset({d.key for d in domains})


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
