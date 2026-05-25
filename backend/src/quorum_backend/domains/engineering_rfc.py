"""
Engineering RFC / Architecture Decision Review.

A fixed reviewer panel deliberates on an engineering proposal (RFC,
design doc, architecture decision) and emits an **Architecture Decision
Record** (ADR) with the recommended decision, the rejected alternatives
and *why* each was rejected, the dissents, and the consequences.

This is the kind of structured review most engineering orgs do badly:
one Slack thread, one meeting, and the rationale evaporates. Quorum's
output makes the deliberation an artifact you can keep, reference, and
revisit when reality catches up to the decision.
"""

from __future__ import annotations

from quorum_backend.domains.base import DomainProfile, ReportSectionSpec, RosterMember
from quorum_backend.pipeline.models import EdgeType, EntityType, Ontology

# --- Engineering RFC ontology -------------------------------------------
_ENTITY_TYPES = [
    EntityType(
        name="Decision",
        description="The architectural choice being made.",
        examples=["Adopt PostgreSQL over MongoDB", "Split monolith into 2 services"],
        is_individual=False,
    ),
    EntityType(
        name="Alternative",
        description="A candidate option being weighed against the others.",
        examples=["status quo", "managed service", "build vs. buy"],
        is_individual=False,
    ),
    EntityType(
        name="Tradeoff",
        description="A dimension along which alternatives differ (latency, cost, complexity, lock-in).",
        examples=["operational complexity", "vendor lock-in", "p99 latency"],
        is_individual=False,
    ),
    EntityType(
        name="Constraint",
        description="A fixed requirement the decision must respect.",
        examples=["budget cap", "Q3 deadline", "SOC 2 control"],
        is_individual=False,
    ),
    EntityType(
        name="Component",
        description="A system component or service affected by the decision.",
        examples=["the auth service", "the data warehouse", "the mobile client"],
        is_individual=False,
    ),
    EntityType(
        name="ExternalDependency",
        description="An outside system, vendor, or library the decision relies on.",
        examples=["AWS RDS", "Stripe", "OpenTelemetry collector"],
        is_individual=False,
    ),
    EntityType(
        name="FailureMode",
        description="A specific way an alternative could fail or degrade.",
        examples=["region-wide outage", "schema migration deadlock"],
        is_individual=False,
    ),
    EntityType(
        name="NonGoal",
        description="Something this decision explicitly does NOT try to solve.",
        examples=["multi-region active-active", "real-time analytics"],
        is_individual=False,
    ),
    EntityType(
        name="Stakeholder",
        description="A team or role downstream of the decision.",
        examples=["the on-call rotation", "the mobile team", "finance"],
        is_individual=False,
    ),
    EntityType(
        name="Reviewer",
        description="A seat in the reviewing panel that deliberates on the decision.",
        examples=["principal engineer", "SRE", "security", "skeptic"],
        is_individual=True,
    ),
]

_EDGE_TYPES = [
    EdgeType(
        name="CONSIDERS",
        description="The decision is weighing this candidate alternative.",
        source_targets=[["Decision", "Alternative"]],
    ),
    EdgeType(
        name="INVOLVES_TRADEOFF",
        description="An alternative is differentiated by this tradeoff dimension.",
        source_targets=[["Alternative", "Tradeoff"]],
    ),
    EdgeType(
        name="CONSTRAINED_BY",
        description="The decision is constrained by this requirement.",
        source_targets=[["Decision", "Constraint"]],
    ),
    EdgeType(
        name="AFFECTS",
        description="An alternative changes the behavior of a system component.",
        source_targets=[["Alternative", "Component"]],
    ),
    EdgeType(
        name="DEPENDS_ON",
        description="An alternative depends on an external system.",
        source_targets=[["Alternative", "ExternalDependency"]],
    ),
    EdgeType(
        name="RISKS",
        description="An alternative is exposed to a specific failure mode.",
        source_targets=[["Alternative", "FailureMode"]],
    ),
    EdgeType(
        name="EXCLUDES",
        description="The decision explicitly excludes a non-goal from scope.",
        source_targets=[["Decision", "NonGoal"]],
    ),
    EdgeType(
        name="IMPACTS",
        description="The decision changes the work or risk surface of a stakeholder.",
        source_targets=[["Decision", "Stakeholder"]],
    ),
    EdgeType(
        name="PREFERRED_OVER",
        description="One alternative dominates another along the relevant dimensions.",
        source_targets=[["Alternative", "Alternative"]],
    ),
    EdgeType(
        name="EVALUATES",
        description="A reviewer evaluates a candidate alternative.",
        source_targets=[["Reviewer", "Alternative"]],
    ),
]

ENGINEERING_RFC_ONTOLOGY = Ontology(entity_types=_ENTITY_TYPES, edge_types=_EDGE_TYPES)


# --- Fixed reviewer panel -----------------------------------------------
# Seven seats, each with a non-overlapping mandate so the debate surfaces
# the trade-offs an organic review usually misses.
_ROSTER = (
    RosterMember(
        role="Principal Engineer",
        name="Principal Engineering",
        bio="Owns overall architectural soundness across the org.",
        persona=(
            "A principal engineer who weighs each alternative against the "
            "long-term architecture, system boundaries, and the bar for "
            "introducing new abstractions. Insists trade-offs are made "
            "explicit and is wary of decisions that quietly increase coupling."
        ),
        expertise=("system design", "architectural coherence", "long-term cost"),
        mandate="Architectural soundness, system boundaries, abstraction discipline.",
        caution=0.6,
    ),
    RosterMember(
        role="Reliability Engineer",
        name="Reliability (SRE)",
        bio="Speaks for the on-call rotation and operational risk.",
        persona=(
            "A site reliability engineer who frames every alternative through "
            "the lens of failure modes, blast radius, recovery time, and the "
            "burden on the on-call rotation. Will reject options that look "
            "elegant but are operationally hostile."
        ),
        expertise=("operational risk", "observability", "on-call burden", "SLOs"),
        mandate="Operational risk, blast radius, on-call burden, SLOs.",
        caution=0.75,
    ),
    RosterMember(
        role="Security Engineer",
        name="Security",
        bio="Models threats and authorization surfaces.",
        persona=(
            "A security engineer who builds the threat model for each "
            "alternative, calls out new authorization surfaces, supply-chain "
            "exposure, and data-handling implications. Skeptical of options "
            "that move sensitive data through more parties."
        ),
        expertise=("threat modeling", "authn/authz", "supply chain", "data handling"),
        mandate="Threat model, authorization surface, supply-chain and data risk.",
        caution=0.75,
    ),
    RosterMember(
        role="Cost & Finance",
        name="Cost",
        bio="Tracks total cost of ownership and vendor lock-in.",
        persona=(
            "An engineer focused on total cost of ownership: not just unit "
            "economics, but vendor lock-in, switching cost, hidden ops cost, "
            "and how the cost curve bends as load grows. Always asks 'and at "
            "10x scale?'"
        ),
        expertise=("TCO", "vendor lock-in", "cost modeling"),
        mandate="Total cost of ownership, lock-in, cost-at-scale.",
        caution=0.6,
    ),
    RosterMember(
        role="Product Manager",
        name="Product",
        bio="Holds the decision to a user/business intent.",
        persona=(
            "A product manager who keeps the conversation tied to user and "
            "business intent. Pushes the panel to be explicit about what "
            "shipping this decision actually unlocks — and what user-visible "
            "outcomes would tell you the decision was right or wrong."
        ),
        expertise=("product intent", "user outcomes", "measurable success"),
        mandate="User and business intent; what success looks like in production.",
        optimism=0.6,
    ),
    RosterMember(
        role="Tech Lead",
        name="Tech Lead",
        bio="Owns team velocity and the learning curve.",
        persona=(
            "The team's tech lead, focused on what the team can actually "
            "execute. Weighs hiring pool, learning curve, ramp-up time, and "
            "the day-to-day developer experience of each alternative."
        ),
        expertise=("team velocity", "DX", "learning curve"),
        mandate="Team velocity, hiring/learning curve, day-to-day developer experience.",
        risk_tolerance=0.55,
    ),
    RosterMember(
        role="Skeptic",
        name="Skeptic",
        bio="Attacks the leading option to fight anchoring.",
        persona=(
            "A devil's-advocate reviewer whose job is to attack whichever "
            "alternative the panel currently favors. Forces the panel to "
            "defend its leading option explicitly rather than slide into "
            "premature consensus."
        ),
        expertise=("debiasing", "anchoring", "premature consensus"),
        mandate="Attack the leading alternative. Force an explicit defense.",
        stance="oppose",
        risk_tolerance=0.55,
        caution=0.5,
    ),
)


# --- Architecture Decision Record outline -------------------------------
_REPORT_OUTLINE = (
    ReportSectionSpec(
        title="Context",
        description=(
            "What triggered this decision and what is the situation today. "
            "Surface the forces that make this an active decision now, not "
            "later. Pull from the brief and any uploaded design docs."
        ),
    ),
    ReportSectionSpec(
        title="Decision drivers",
        description=(
            "The constraints the decision must respect and the trade-off "
            "dimensions the panel is weighing — cost, latency, operational "
            "complexity, lock-in, time-to-ship. Be concrete."
        ),
    ),
    ReportSectionSpec(
        title="Alternatives considered",
        description=(
            "Each candidate option in one paragraph, with the headline "
            "trade-off and the failure mode that worries the panel most."
        ),
    ),
    ReportSectionSpec(
        title="Recommended decision",
        description=(
            "The panel's converged recommendation and the rationale. Explain "
            "what it unlocks and why now is the right time for it."
        ),
    ),
    ReportSectionSpec(
        title="Why not the alternatives",
        description=(
            "Explicit rejection rationale for each non-chosen alternative. "
            "This is the documentation gap an organic ADR almost always misses."
        ),
    ),
    ReportSectionSpec(
        title="Dissents",
        description=(
            "Reviewers who pushed back on the recommendation and the basis "
            "for their disagreement, preserved verbatim. Quote them; do not "
            "paraphrase them away. If no dissent emerged, say so explicitly."
        ),
    ),
    ReportSectionSpec(
        title="Consequences and risks",
        description=(
            "What the panel expects to be true 3, 6, and 12 months after "
            "this decision ships. Name the failure modes and the early "
            "warning signs the SRE seat flagged."
        ),
    ),
    ReportSectionSpec(
        title="Follow-ups and open questions",
        description=(
            "Work this decision creates or unblocks, prerequisites to track, "
            "and the conditions under which the panel would revisit the call."
        ),
    ),
)


ENGINEERING_RFC_DOMAIN = DomainProfile(
    key="engineering_rfc",
    name="Engineering RFC / ADR",
    description=(
        "A multi-disciplinary reviewer panel debates an architecture "
        "decision or RFC and emits an Architecture Decision Record — "
        "recommended decision, alternatives considered, why not each, "
        "dissents, consequences. Decision support for the engineering "
        "team, not autonomous architectural authority."
    ),
    fixed_ontology=ENGINEERING_RFC_ONTOLOGY,
    fixed_agent_roster=_ROSTER,
    fixed_report_outline=_REPORT_OUTLINE,
    report_title_template="ADR — {project_title}",
    report_summary=(
        "Multi-disciplinary review-panel deliberation on the decision "
        "below. Decision support — the engineering team owns the call."
    ),
    report_section_system_prompt=(
        "You are writing one section of an Architecture Decision Record "
        "produced by a multi-disciplinary review panel. Write in concrete, "
        "engineering prose: name specific trade-offs, components, and "
        "failure modes; avoid platitudes. Quote reviewer agents verbatim "
        "with `>` blockquote syntax where their reasoning supports a point. "
        "Do not invent details the deliberation did not produce. Output "
        "200-400 words of markdown body — no headings."
    ),
    report_provenance_footer=True,
    report_provenance_disclaimer=(
        "This ADR is decision support produced by a virtual review panel. "
        "The engineering team owns the final decision and is responsible "
        "for validating the trade-offs against the current system state."
    ),
)
