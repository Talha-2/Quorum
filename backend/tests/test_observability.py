"""Tests for observability — structured logging and LLM metrics (Phase 1)."""

import json
import logging
import os
import shutil
import tempfile
from pathlib import Path

os.environ.setdefault("LLM_PROVIDER", "local")

from fastapi.testclient import TestClient

from quorum_backend import llm, main
from quorum_backend.observability import JsonLogFormatter, LLMMetrics, llm_metrics
from quorum_backend.pipeline import router as pipeline_router


def _make_test_dir() -> Path:
    workspace_root = Path(__file__).resolve().parents[2]
    return Path(tempfile.mkdtemp(prefix="quorum-pipeline-test-", dir=str(workspace_root)))


def _reset_state(test_dir: Path):
    pipeline_router.clear_project_store_for_tests()
    llm._llm_provider = None
    llm_metrics.reset()


# --- Structured logging --------------------------------------------------

def test_json_log_formatter_emits_valid_json():
    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="quorum.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    parsed = json.loads(formatter.format(record))
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "quorum.test"
    assert parsed["message"] == "hello world"


# --- Metrics collector ---------------------------------------------------

def test_llm_metrics_aggregates_calls():
    metrics = LLMMetrics()
    metrics.record("google", latency_ms=120.0, prompt_chars=400, completion_chars=400, ok=True)
    metrics.record("google", latency_ms=80.0, prompt_chars=400, completion_chars=400, ok=False)

    snap = metrics.snapshot()
    assert snap["totals"]["calls"] == 2
    assert snap["totals"]["failures"] == 1
    assert snap["totals"]["avg_latency_ms"] == 100.0
    # (400 + 400) chars per call * 2 calls / 4 chars-per-token = 400
    assert snap["providers"]["google"]["estimated_tokens"] == 400


# --- Metrics endpoint and instrumentation -------------------------------

def test_metrics_endpoint_records_llm_calls():
    test_dir = _make_test_dir()
    _reset_state(test_dir)
    try:
        with TestClient(main.app) as client:
            empty = client.get("/api/metrics")
            assert empty.status_code == 200
            assert empty.json()["llm"]["totals"]["calls"] == 0

            # The graph + persona stages call the (local) LLM provider.
            project_id = client.post(
                "/api/projects", json={"brief": "Should we adopt the new workflow?"}
            ).json()["id"]
            client.post(f"/api/projects/{project_id}/graph/ontology/generate", json={})
            client.post(f"/api/projects/{project_id}/graph/build", json={})

            metrics = client.get("/api/metrics").json()
            assert metrics["llm"]["totals"]["calls"] > 0
            assert "local" in metrics["llm"]["providers"]
            assert metrics["projects"]["count"] == 1
    finally:
        shutil.rmtree(test_dir, ignore_errors=True)
