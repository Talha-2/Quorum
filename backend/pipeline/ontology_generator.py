"""
Ontology generation service.

Takes the brief + optional document context, asks the LLM to design an
ontology of entity types and edge types appropriate to the topic. Constrained
to a small, well-formed schema so the downstream graph builder produces a
clean, useful graph.

Output shape: 8 concrete entity types + Person + Organization fallbacks
(10 total) and 6-10 edge types in UPPER_SNAKE_CASE.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Optional

try:
    from ..llm import get_llm
except ImportError:  # pragma: no cover
    from llm import get_llm

from .models import EdgeType, EntityType, Ontology

logger = logging.getLogger(__name__)


ONTOLOGY_SYSTEM_PROMPT = """You are an ontology designer for a multi-agent simulation engine.

Given a research brief, you design the schema (entity types + relationship types)
that the simulation will use to model the world.

You return ONLY a JSON object with this exact shape:

{
  "entity_types": [
    {
      "name": "PascalCase",
      "description": "one sentence",
      "examples": ["example A", "example B", "example C"],
      "is_individual": true
    }
  ],
  "edge_types": [
    {
      "name": "UPPER_SNAKE_CASE",
      "description": "one sentence",
      "source_targets": [["EntityTypeA", "EntityTypeB"]]
    }
  ]
}

Hard rules:
- entity_types must contain EXACTLY 10 items
- The first 8 must be concrete, topic-specific types
- The last 2 must be the fallbacks: "Person" (is_individual: true) and "Organization" (is_individual: false)
- edge_types must contain between 6 and 10 items
- Edge type names use UPPER_SNAKE_CASE (e.g. REPORTS_ON, AFFILIATED_WITH)
- Each edge_type must list 1-3 valid (source, target) entity-type name pairs
- "is_individual" is true for entity types representing single people, false for groups/organizations/abstract things
- Output ONLY the JSON object, no markdown fences, no commentary
"""


ONTOLOGY_USER_TEMPLATE = """RESEARCH BRIEF:
{brief}

CONTEXT:
{context}

Design the ontology for this brief. Output the JSON object only.
"""


def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def _parse_ontology_json(raw: str) -> Optional[dict]:
    cleaned = _strip_markdown_fences(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def _validate_and_normalize(parsed: dict) -> Optional[Ontology]:
    if not isinstance(parsed, dict):
        return None

    raw_entities = parsed.get("entity_types") or []
    raw_edges = parsed.get("edge_types") or []
    if not isinstance(raw_entities, list) or not isinstance(raw_edges, list):
        return None

    entity_types: list[EntityType] = []
    for item in raw_entities:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        # Force PascalCase-ish: keep alphanumeric, capitalize first letter
        name = re.sub(r"[^A-Za-z0-9]", "", name)
        if not name:
            continue
        name = name[0].upper() + name[1:]
        entity_types.append(
            EntityType(
                name=name,
                description=str(item.get("description") or "").strip(),
                examples=[str(x).strip() for x in (item.get("examples") or [])][:5],
                is_individual=bool(item.get("is_individual", True)),
            )
        )

    edge_types: list[EdgeType] = []
    for item in raw_edges:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        # Force UPPER_SNAKE_CASE
        name = re.sub(r"[^A-Za-z0-9_]", "_", name).upper().strip("_")
        if not name:
            continue
        targets_raw = item.get("source_targets") or []
        targets: list[list[str]] = []
        for pair in targets_raw:
            if isinstance(pair, (list, tuple)) and len(pair) == 2:
                targets.append([str(pair[0]), str(pair[1])])
        edge_types.append(
            EdgeType(
                name=name,
                description=str(item.get("description") or "").strip(),
                source_targets=targets,
            )
        )

    # Ensure fallbacks are present
    names_lower = {e.name.lower() for e in entity_types}
    if "person" not in names_lower:
        entity_types.append(
            EntityType(
                name="Person",
                description="An individual person whose role isn't covered by the other types",
                examples=["unaffiliated commentator"],
                is_individual=True,
            )
        )
    if "organization" not in names_lower:
        entity_types.append(
            EntityType(
                name="Organization",
                description="A group or institution whose role isn't covered by the other types",
                examples=["NGO", "trade association"],
                is_individual=False,
            )
        )

    # Trim or pad to exactly 10
    if len(entity_types) > 10:
        # Keep first 8 + Person + Organization
        concrete = [e for e in entity_types if e.name.lower() not in {"person", "organization"}][:8]
        person = next(e for e in entity_types if e.name.lower() == "person")
        org = next(e for e in entity_types if e.name.lower() == "organization")
        entity_types = concrete + [person, org]
    elif len(entity_types) < 10:
        # Add generic padding (rare path)
        for i in range(10 - len(entity_types)):
            entity_types.append(
                EntityType(
                    name=f"Topic{i + 1}",
                    description="Auto-padded topic-specific entity",
                    examples=[],
                    is_individual=False,
                )
            )

    # Trim edges to 10
    if len(edge_types) > 10:
        edge_types = edge_types[:10]
    if len(edge_types) < 4:
        # Pad with generic edges
        defaults = [
            EdgeType("RELATES_TO", "Generic relationship", [["Person", "Person"]]),
            EdgeType("AFFILIATED_WITH", "Affiliation between two parties", [["Person", "Organization"]]),
            EdgeType("OPPOSES", "Opposing stance", [["Person", "Person"]]),
            EdgeType("SUPPORTS", "Supporting stance", [["Person", "Person"]]),
        ]
        existing = {e.name for e in edge_types}
        for d in defaults:
            if d.name not in existing and len(edge_types) < 6:
                edge_types.append(d)

    return Ontology(entity_types=entity_types, edge_types=edge_types)


async def generate_ontology(brief: str, context: str = "") -> Optional[Ontology]:
    """Generate an ontology for the given brief using the LLM.

    Returns None on failure (caller should handle by surfacing an error to the
    user — there's no static fallback because the ontology is necessarily
    topic-specific).
    """
    if not brief or not brief.strip():
        return None

    user_message = ONTOLOGY_USER_TEMPLATE.format(
        brief=brief.strip(),
        context=(context or "No additional context provided.").strip(),
    )

    try:
        llm = get_llm()
        # 3000 base + Azure provider's reasoning budget (3000) = 6000 effective.
        # An ontology with 10 entity types + 10 edge types averages ~1500 tokens
        # of pure JSON, so this gives Kimi-style reasoning models 4500 tokens
        # of think-room.
        raw = await llm.generate(
            system=ONTOLOGY_SYSTEM_PROMPT,
            user_message=user_message,
            max_tokens=3000,
        )
    except Exception as exc:
        logger.warning("Ontology LLM call failed: %s", exc)
        return None

    if not raw or not raw.strip():
        return None

    parsed = _parse_ontology_json(raw)
    if parsed is None:
        logger.warning("Could not parse ontology JSON. Raw start: %s", (raw or "")[:200])
        return None

    ontology = _validate_and_normalize(parsed)
    if ontology is None or not ontology.entity_types:
        logger.warning("Validated ontology was empty.")
        return None

    return ontology
