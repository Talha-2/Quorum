"""Tests for the evaluation harness (Phase 2)."""

import asyncio
import os

os.environ.setdefault("LLM_PROVIDER", "local")

from quorum_backend.eval import CASES, EvalCase, run_case, run_suite, score_report
from quorum_backend.eval.scoring import Score


def test_score_report_passes_when_rubric_matches():
    case = EvalCase(
        name="synthetic",
        domain="oncology_mdt",
        brief="x",
        expected_section_titles=["A", "B"],
        required_markdown_terms=["disclaimer"],
        require_provenance=True,
    )
    report = {
        "sections": [{"title": "A"}, {"title": "B"}],
        "markdown": "## Provenance\nDisclaimer: foo",
    }
    s = score_report(case, report)
    assert s.passed is True
    assert s.checks == {
        "has_sections": True,
        "section_order": True,
        "required_terms": True,
        "provenance": True,
    }


def test_score_report_flags_section_order_mismatch():
    case = EvalCase(
        name="bad",
        domain="oncology_mdt",
        brief="x",
        expected_section_titles=["A", "B"],
        require_provenance=False,
    )
    report = {"sections": [{"title": "B"}, {"title": "A"}], "markdown": ""}
    s = score_report(case, report)
    assert s.passed is False
    assert s.checks["section_order"] is False


def test_run_case_for_oncology_brief_passes_rubric():
    case = next(c for c in CASES if c.name == "oncology_her2_iia")
    result = asyncio.run(run_case(case))
    assert result.error is None
    assert result.score.passed, result.score.notes


def test_run_case_for_dx_education_brief_passes_rubric():
    case = next(c for c in CASES if c.name == "dx_thunderclap_headache")
    result = asyncio.run(run_case(case))
    assert result.error is None
    assert result.score.passed, result.score.notes


def test_run_suite_passes_every_curated_case():
    results = asyncio.run(run_suite())
    failures = [r for r in results if not r.score.passed]
    assert not failures, [
        f"{r.case.name}: {r.score.notes}" for r in failures
    ]
    assert len(results) == len(CASES)
