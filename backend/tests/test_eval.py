"""Tests for the evaluation harness."""

import asyncio
import os

os.environ.setdefault("LLM_PROVIDER", "local")

from quorum_backend.eval import CASES, EvalCase, run_case, run_suite, score_report


def test_score_report_passes_when_rubric_matches():
    case = EvalCase(
        name="synthetic",
        domain="engineering_rfc",
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
        domain="engineering_rfc",
        brief="x",
        expected_section_titles=["A", "B"],
        require_provenance=False,
    )
    report = {"sections": [{"title": "B"}, {"title": "A"}], "markdown": ""}
    s = score_report(case, report)
    assert s.passed is False
    assert s.checks["section_order"] is False


def test_run_case_for_engineering_rfc_brief_passes_rubric():
    case = next(c for c in CASES if c.name == "rfc_postgres_over_mongo")
    result = asyncio.run(run_case(case))
    assert result.error is None
    assert result.score.passed, result.score.notes


def test_run_case_for_second_engineering_rfc_brief_passes_rubric():
    case = next(c for c in CASES if c.name == "rfc_split_monolith")
    result = asyncio.run(run_case(case))
    assert result.error is None
    assert result.score.passed, result.score.notes


def test_run_suite_passes_every_curated_case():
    results = asyncio.run(run_suite())
    failures = [r for r in results if not r.score.passed]
    assert not failures, [f"{r.case.name}: {r.score.notes}" for r in failures]
    assert len(results) == len(CASES)
