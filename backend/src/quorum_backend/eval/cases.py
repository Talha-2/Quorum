"""Curated evaluation cases.

Each case is a self-contained input + a rubric the runner scores against.
The rubric checks invariants that hold regardless of LLM provider — the
deterministic structure that the domain profile pins. Richer content
checks can be added per-case when running against a real LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

# Section orders pulled from the domain profiles so they stay in sync.
def _oncology_section_titles() -> List[str]:
    from quorum_backend.domains.oncology import ONCOLOGY_MDT_DOMAIN

    return [s.title for s in ONCOLOGY_MDT_DOMAIN.fixed_report_outline]


def _dx_section_titles() -> List[str]:
    from quorum_backend.domains.dx_education import DX_EDUCATION_DOMAIN

    return [s.title for s in DX_EDUCATION_DOMAIN.fixed_report_outline]


@dataclass
class EvalCase:
    """One input case + the rubric the runner scores against."""

    name: str
    """Stable identifier for the case (used in the scorecard)."""

    domain: str
    """Domain key the case is evaluated under."""

    brief: str
    """The brief the pipeline is run on."""

    title: str = ""
    """Optional project title."""

    expected_section_titles: List[str] = field(default_factory=list)
    """Section titles the report must contain, in order."""

    required_markdown_terms: List[str] = field(default_factory=list)
    """Substrings (case-insensitive) the report markdown must contain."""

    require_provenance: bool = True
    """Whether the report must include the Provenance footer."""


CASES: List[EvalCase] = [
    EvalCase(
        name="oncology_her2_iia",
        domain="oncology_mdt",
        title="HER2+ stage IIA case",
        brief=(
            "A 64-year-old patient with newly diagnosed HER2-positive stage "
            "IIA invasive ductal carcinoma. ECOG 0. Comorbidities include "
            "well-controlled hypertension. The board is asked to discuss "
            "neoadjuvant systemic therapy options and surgical planning."
        ),
        expected_section_titles=_oncology_section_titles(),
        required_markdown_terms=[
            "Tumor Board Brief",
            "Provenance",
            "Disclaimer",
            "decision support",
        ],
    ),
    EvalCase(
        name="oncology_nsclc_iiia",
        domain="oncology_mdt",
        title="Stage IIIA NSCLC, EGFR exon 19",
        brief=(
            "A 72-year-old former smoker with stage IIIA non-small-cell lung "
            "cancer harbouring an EGFR exon 19 deletion. Comorbidities: "
            "chronic kidney disease stage 3a, well-controlled diabetes."
        ),
        expected_section_titles=_oncology_section_titles(),
        required_markdown_terms=["Tumor Board Brief", "Provenance"],
    ),
    EvalCase(
        name="dx_acute_chest_pain",
        domain="quorum_dx_education",
        title="Acute chest pain vignette",
        brief=(
            "A 56-year-old smoker with sudden onset substernal chest pressure "
            "radiating to the left arm, diaphoresis, and shortness of breath. "
            "Vital signs notable for hypertension and tachycardia."
        ),
        expected_section_titles=_dx_section_titles(),
        required_markdown_terms=[
            "Differential Diagnosis Brief",
            "education only",
            "Provenance",
        ],
    ),
    EvalCase(
        name="dx_thunderclap_headache",
        domain="quorum_dx_education",
        title="Thunderclap headache",
        brief=(
            "A 44-year-old presenting with a sudden severe headache reaching "
            "maximum intensity within seconds, associated with brief loss of "
            "consciousness and neck stiffness."
        ),
        expected_section_titles=_dx_section_titles(),
        required_markdown_terms=["Differential Diagnosis Brief", "education only"],
    ),
    EvalCase(
        name="general_smoke",
        domain="general",
        title="Generic strategy brief",
        brief="Should we adopt the new coordination workflow next quarter?",
        # General domain does not pin sections — only assert non-emptiness.
        expected_section_titles=[],
        required_markdown_terms=[],
        require_provenance=False,
    ),
]
