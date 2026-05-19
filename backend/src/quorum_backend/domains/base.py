"""
Domain profiles.

A :class:`DomainProfile` specializes the generic Quorum pipeline for one
application area. It is the extension point that turns the domain-agnostic
engine into a focused product (e.g. an oncology tumor board).

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

    For a clinical domain the panel is a standing roster (the MDT specialists),
    not entities extracted from the case. A roster member is turned into an
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
class DomainProfile:
    """Configuration that specializes the pipeline for one application area."""

    key: str
    """Stable identifier persisted on the project (e.g. ``"oncology_mdt"``)."""

    name: str
    """Human-readable name shown in the UI."""

    description: str
    """One- or two-sentence summary of what this domain is for."""

    fixed_ontology: Optional[Ontology] = None
    """When set, stage 01 uses this ontology instead of an LLM call."""

    fixed_agent_roster: Tuple[RosterMember, ...] = field(default_factory=tuple)
    """When non-empty, stage 03 builds the panel from this roster."""

    @property
    def uses_fixed_ontology(self) -> bool:
        return self.fixed_ontology is not None

    @property
    def uses_fixed_roster(self) -> bool:
        return len(self.fixed_agent_roster) > 0
