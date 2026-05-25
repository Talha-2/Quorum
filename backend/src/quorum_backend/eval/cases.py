"""Curated evaluation cases.

Each case is a self-contained input + a rubric the runner scores against.
The rubric checks invariants that hold regardless of LLM provider — the
deterministic structure that the domain profile pins. Richer content
checks can be added per-case when running against a real LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


def _engineering_rfc_section_titles() -> List[str]:
    from quorum_backend.domains.engineering_rfc import ENGINEERING_RFC_DOMAIN

    return [s.title for s in ENGINEERING_RFC_DOMAIN.fixed_report_outline]


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
        name="rfc_postgres_over_mongo",
        domain="engineering_rfc",
        title="Adopt PostgreSQL over MongoDB for the orders service",
        brief=(
            "The orders service currently runs on a sharded MongoDB cluster "
            "and has outgrown the operational burden. The team is weighing "
            "migrating to managed PostgreSQL (AWS RDS) versus staying on "
            "MongoDB and investing in stronger schema enforcement. "
            "Constraints: a 1-quarter migration budget, no downtime windows "
            "longer than 5 minutes, and the existing analytics pipeline "
            "expects relational joins."
        ),
        expected_section_titles=_engineering_rfc_section_titles(),
        required_markdown_terms=["ADR", "Provenance", "decision support"],
    ),
    EvalCase(
        name="rfc_split_monolith",
        domain="engineering_rfc",
        title="Carve the billing path out of the monolith",
        brief=(
            "The monolithic checkout app has grown to the point where billing "
            "deploys are gated on the entire app's test suite. The team is "
            "considering carving billing into a separate service. "
            "Alternatives include leaving it in place with a stricter module "
            "boundary, or extracting only the invoice generator first. "
            "Constraints: PCI scope must not expand; on-call rotation is small."
        ),
        expected_section_titles=_engineering_rfc_section_titles(),
        required_markdown_terms=["ADR", "Provenance"],
    ),
    EvalCase(
        name="rfc_observability_stack",
        domain="engineering_rfc",
        title="Pick the next observability stack",
        brief=(
            "The current self-hosted Prometheus/Grafana setup has hit "
            "scaling and on-call cost limits. The team is choosing between "
            "Datadog, Grafana Cloud, and continuing self-hosted with a "
            "dedicated SRE on the rotation. The business is sensitive to "
            "data-egress cost; the security team requires PII never leaves "
            "the VPC."
        ),
        expected_section_titles=_engineering_rfc_section_titles(),
        required_markdown_terms=["ADR", "Provenance"],
    ),
    EvalCase(
        name="rfc_oauth_idp",
        domain="engineering_rfc",
        title="Standardize on a single identity provider",
        brief=(
            "Three internal apps currently use different identity providers. "
            "The team wants to standardize on one. Candidates: Okta, a "
            "self-hosted Keycloak deployment, or AWS Cognito. Constraints: "
            "SOC 2 controls, an existing SAML integration with the HR system, "
            "and a 6-month rollout window."
        ),
        expected_section_titles=_engineering_rfc_section_titles(),
        required_markdown_terms=["ADR", "Provenance"],
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
