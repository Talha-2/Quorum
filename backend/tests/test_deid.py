"""Tests for the de-identification gate at upload (Phase 2)."""

import os
import shutil
import tempfile
from pathlib import Path

os.environ.setdefault("LLM_PROVIDER", "local")

from fastapi.testclient import TestClient

from quorum_backend import llm, main
from quorum_backend.config import settings
from quorum_backend.pipeline import router as pipeline_router
from quorum_backend.pipeline.deid import DeidMode, redact, scan_for_phi, summary


def _make_test_dir() -> Path:
    workspace_root = Path(__file__).resolve().parents[2]
    return Path(tempfile.mkdtemp(prefix="quorum-pipeline-test-", dir=str(workspace_root)))


def _reset_state(test_dir: Path):
    pipeline_router.clear_project_store_for_tests()
    llm._llm_provider = None


# --- Pattern unit tests --------------------------------------------------

def test_scan_detects_ssn_phone_email():
    text = (
        "Reach the family at 310-555-1212 or care@example.org. "
        "SSN on file 123-45-6789."
    )
    findings = scan_for_phi(text)
    kinds = {f.kind for f in findings}
    assert kinds == {"ssn", "phone", "email"}


def test_scan_detects_context_keyed_mrn_and_dob():
    text = "MRN: A1234567\nDate of Birth: 03/14/1957\nNot a real ID 99."
    findings = scan_for_phi(text)
    kinds = {f.kind for f in findings}
    assert "mrn" in kinds and "dob" in kinds


def test_scan_ignores_bare_dates_without_dob_context():
    # A bare date (e.g. "Visit 03/14/2026") has too high a false-positive
    # rate to flag without context — verify we do NOT flag it as DOB.
    text = "Patient seen on 03/14/2026; follow-up planned."
    findings = scan_for_phi(text)
    kinds = {f.kind for f in findings}
    assert "dob" not in kinds


def test_redact_replaces_with_kind_placeholder():
    text = "Call (310) 555-1212 today."
    redacted, finds = redact(text)
    assert len(finds) == 1
    assert "(310) 555-1212" not in redacted
    assert "[REDACTED:phone]" in redacted


def test_summary_counts_findings_by_kind():
    text = "a@b.com and c@d.com — call 310-555-1212."
    counts = summary(scan_for_phi(text))
    assert counts == {"email": 2, "phone": 1}


def test_deidmode_parse_accepts_strings_and_falls_back():
    assert DeidMode.parse("strict") is DeidMode.STRICT
    assert DeidMode.parse("REDACT") is DeidMode.REDACT
    assert DeidMode.parse("nonsense") is DeidMode.WARN
    assert DeidMode.parse(None) is DeidMode.WARN


# --- Upload-endpoint integration tests -----------------------------------

def test_upload_in_warn_mode_attaches_findings_but_allows_upload():
    test_dir = _make_test_dir()
    _reset_state(test_dir)
    saved_mode = settings.deid_mode
    settings.deid_mode = "warn"
    try:
        with TestClient(main.app) as client:
            project_id = client.post(
                "/api/projects", json={"brief": "Case review."}
            ).json()["id"]

            resp = client.post(
                f"/api/projects/{project_id}/upload",
                files={
                    "file": (
                        "case.txt",
                        b"Contact: care@example.org, SSN 123-45-6789.",
                        "text/plain",
                    )
                },
            )
            assert resp.status_code == 200
            doc = resp.json()["uploaded_documents"][0]
            assert doc["phi_findings_count"] >= 2
            assert doc["phi_redacted"] is False
    finally:
        settings.deid_mode = saved_mode
        shutil.rmtree(test_dir, ignore_errors=True)


def test_upload_in_strict_mode_rejects_phi():
    test_dir = _make_test_dir()
    _reset_state(test_dir)
    saved_mode = settings.deid_mode
    settings.deid_mode = "strict"
    try:
        with TestClient(main.app) as client:
            project_id = client.post(
                "/api/projects", json={"brief": "Case review."}
            ).json()["id"]
            resp = client.post(
                f"/api/projects/{project_id}/upload",
                files={
                    "file": ("case.txt", b"SSN 123-45-6789 on file.", "text/plain")
                },
            )
            assert resp.status_code == 400
            assert "phi" in resp.json()["detail"].lower()
    finally:
        settings.deid_mode = saved_mode
        shutil.rmtree(test_dir, ignore_errors=True)


def test_upload_in_redact_mode_replaces_phi_in_stored_text():
    test_dir = _make_test_dir()
    _reset_state(test_dir)
    saved_mode = settings.deid_mode
    settings.deid_mode = "redact"
    try:
        with TestClient(main.app) as client:
            project_id = client.post(
                "/api/projects", json={"brief": "Case review."}
            ).json()["id"]
            resp = client.post(
                f"/api/projects/{project_id}/upload",
                files={
                    "file": (
                        "case.txt",
                        b"Reach me at 310-555-1212 please.",
                        "text/plain",
                    )
                },
            )
            assert resp.status_code == 200
            doc = resp.json()["uploaded_documents"][0]
            assert doc["phi_redacted"] is True
            # The router stores the redacted text in project.uploaded_documents.
            project = pipeline_router._projects[project_id]
            stored_text = project.uploaded_documents[0]["text"]
            assert "310-555-1212" not in stored_text
            assert "[REDACTED:phone]" in stored_text
    finally:
        settings.deid_mode = saved_mode
        shutil.rmtree(test_dir, ignore_errors=True)
