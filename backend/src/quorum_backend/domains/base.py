"""
Domain profiles.

A :class:`DomainProfile` specializes the generic Quorum pipeline for one
application area. It is the extension point that turns the domain-agnostic
engine into a focused product (e.g. an engineering RFC reviewer).

Phase 1 wires one capability: a fixed ontology. When a domain supplies one,
stage 01 applies it verbatim instead of asking the LLM to invent a schema —
which is faster, deterministic, and auditable (important for clinical use).
Later phases extend this profile with a fixed agent roster and a domain
report template; those fields are intentionally not present yet so the
abstraction only exposes what is actually wired.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

from quorum_backend.pipeline.models import Ontology


@dataclass(frozen=True)
class RosterMember:
    """One member of a domain's fixed agent panel.

    For a specialized domain (e.g. engineering RFC review) the panel is a
    standing roster — the reviewer seats — not entities extracted from the
    brief. A roster member is turned into an
    :class:`~quorum_backend.pipeline.models.AgentProfile` deterministically —
    no LLM call — which keeps the panel reproducible and auditable.
    """

    role: str
    """Short title, e.g. "Medical Oncologist"."""

    name: str
    """Display name shown in the debate UI, e.g. "Medical Oncology"."""

    bio: str
    """One-line description of the seat."""

    persona: str
    """System-prompt context: how this specialist reasons and argues."""

    expertise: Tuple[str, ...] = ()
    mandate: str = ""
    """What this seat is responsible for raising in the deliberation."""

    stance: str = "neutral"
    optimism: float = 0.5
    risk_tolerance: float = 0.5
    caution: float = 0.5
    bias: str = ""


@dataclass(frozen=True)
class ReportSectionSpec:
    """One section of a domain's fixed report outline."""

    title: str
    description: str
    """Hint the section writer uses to ground the LLM-written body."""


@dataclass(frozen=True)
class DomainProfile:
    """Configuration that specializes the pipeline for one application area."""

    key: str
    """Stable identifier persisted on the project (e.g. ``"engineering_rfc"``)."""

    name: str
    """Human-readable name shown in the UI."""

    description: str
    """One- or two-sentence summary of what this domain is for."""

    fixed_ontology: Optional[Ontology] = None
    """When set, stage 01 uses this ontology instead of an LLM call."""

    fixed_agent_roster: Tuple[RosterMember, ...] = field(default_factory=tuple)
    """When non-empty, stage 03 builds the panel from this roster."""

    fixed_report_outline: Tuple[ReportSectionSpec, ...] = field(default_factory=tuple)
    """When non-empty, stage 07 uses this outline instead of LLM planning."""

    report_title_template: Optional[str] = None
    """Format string with ``{project_title}`` for the report's H1."""

    report_summary: Optional[str] = None
    """Fixed one-line summary placed under the title. ``None`` falls back."""

    report_section_system_prompt: Optional[str] = None
    """Domain-tuned system prompt for the per-section LLM call."""

    report_provenance_footer: bool = False
    """Append a deterministic provenance/disclaimer footer to the markdown."""

    report_provenance_disclaimer: Optional[str] = None
    """Domain-specific disclaimer line for the footer. Falls back to a
    generic 'decision support, not a substitute for human judgment' line."""

    full_panel_per_round: bool = False
    """When True, every seat in the fixed roster speaks every round (instead
    of the default stride-sampled subset). Use when the roster is the moat
    and partial coverage would defeat the point."""

    cross_examiner_role: Optional[str] = None
    """When set, the roster member with this ``role`` gets one extra turn at
    the end of each round explicitly prompted to attack the round's leading
    argument. Used to make the Skeptic seat earn its keep."""

    skip_simulation_config: bool = False
    """When True, stage 04 (sim config) returns a deterministic minimal
    config instead of an LLM call. The social-media-sim time/platform
    configs are irrelevant for a fixed-roster RFC review."""

    skip_activation: bool = False
    """When True, stage 05 (activation) returns a deterministic empty
    activation instead of an LLM call. For RFC review the brief IS the
    activation; the panel doesn't need a 'narrative direction' to deliberate."""

    @property
    def uses_fixed_ontology(self) -> bool:
        return self.fixed_ontology is not None

    @property
    def uses_fixed_roster(self) -> bool:
        return len(self.fixed_agent_roster) > 0

    @property
    def uses_fixed_report(self) -> bool:
        return len(self.fixed_report_outline) > 0
