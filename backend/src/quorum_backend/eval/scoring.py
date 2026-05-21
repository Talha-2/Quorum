"""Score a generated report against an :class:`EvalCase` rubric."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from quorum_backend.eval.cases import EvalCase


@dataclass
class Score:
    """Scorecard for one case run."""

    case_name: str
    passed: bool
    checks: Dict[str, bool] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    @property
    def pass_count(self) -> int:
        return sum(1 for v in self.checks.values() if v)

    @property
    def total(self) -> int:
        return len(self.checks)

    def __str__(self) -> str:
        verdict = "PASS" if self.passed else "FAIL"
        body = ", ".join(f"{k}={'✓' if v else '✗'}" for k, v in self.checks.items())
        return f"[{verdict}] {self.case_name}  {self.pass_count}/{self.total}  {body}"


def score_report(case: EvalCase, report: Dict[str, Any]) -> Score:
    """Compare a generated report to ``case``'s rubric."""
    checks: Dict[str, bool] = {}
    notes: List[str] = []

    sections = report.get("sections") or []
    section_titles = [s.get("title", "") for s in sections]
    markdown = report.get("markdown") or ""
    md_lower = markdown.lower()

    # 1. A report exists and has sections.
    checks["has_sections"] = bool(sections)
    if not sections:
        notes.append("report has no sections")

    # 2. Section ordering matches the rubric exactly (where pinned).
    if case.expected_section_titles:
        match = section_titles == list(case.expected_section_titles)
        checks["section_order"] = match
        if not match:
            notes.append(
                f"section titles mismatch: got {section_titles}, "
                f"expected {case.expected_section_titles}"
            )

    # 3. Required substrings present in the markdown.
    if case.required_markdown_terms:
        all_present = True
        for term in case.required_markdown_terms:
            if term.lower() not in md_lower:
                all_present = False
                notes.append(f"required term not found in markdown: {term!r}")
        checks["required_terms"] = all_present

    # 4. Provenance footer present when required.
    if case.require_provenance:
        present = "## Provenance" in markdown
        checks["provenance"] = present
        if not present:
            notes.append("provenance footer missing")

    passed = all(checks.values()) if checks else False
    return Score(case_name=case.name, passed=passed, checks=checks, notes=notes)
