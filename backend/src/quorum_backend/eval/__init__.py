"""
Evaluation harness for Quorum's pipeline.

Curated cases are run through the full pipeline programmatically and the
output is scored against a fixed rubric. The harness has three jobs:

1. Catch regressions in the deterministic structure of clinical briefs
   (section ordering, provenance footer, disclaimers) — the part of the
   output we can guarantee regardless of LLM provider.

2. Provide a place to attach richer LLM-judged scoring later (guideline
   concordance, can't-miss recall, dissent quality) without changing the
   runner or case format.

3. Give a CLI for ad-hoc scorecards during development.
"""

from quorum_backend.eval.cases import CASES, EvalCase
from quorum_backend.eval.runner import EvalResult, run_case, run_suite
from quorum_backend.eval.scoring import Score, score_report

__all__ = [
    "CASES",
    "EvalCase",
    "EvalResult",
    "Score",
    "run_case",
    "run_suite",
    "score_report",
]
