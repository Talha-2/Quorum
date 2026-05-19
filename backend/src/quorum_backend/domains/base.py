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

from dataclasses import dataclass
from typing import Optional

from quorum_backend.pipeline.models import Ontology


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

    @property
    def uses_fixed_ontology(self) -> bool:
        return self.fixed_ontology is not None
