"""
GraphRAG-lite — in-memory graph extraction.

Quorum's in-memory implementation extracts entities + relations from the
brief + ontology in a single LLM call: given the brief and the ontology
schema, return all entities and relations as JSON.

The interface is intentionally narrow so a future Zep impl can drop in:

    builder = ZepGraphBuilder(client)
    graph = await builder.build(brief, ontology)

versus the current:

    builder = InMemoryGraphBuilder()
    graph = await builder.build(brief, ontology)
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

from .models import (
    GraphEntityNode,
    GraphRelationEdge,
    KnowledgeGraph,
    Ontology,
    make_edge_id,
    make_entity_id,
)

logger = logging.getLogger(__name__)


GRAPH_EXTRACTION_PROMPT = """You are an information extraction engine.

You will be given a research brief and an ONTOLOGY (entity types + edge types).
Extract every concrete real-world entity that the brief implies, and every
relationship between them. Use ONLY the entity types and edge types from the
ontology — do not invent new ones.

Return ONLY a JSON object with this exact shape:

{
  "nodes": [
    {
      "name": "concrete name of the entity (e.g. 'Wuhan University', 'Dr. Helena Marsh')",
      "type": "EntityTypeName from the ontology",
      "description": "one sentence about who/what they are and why they matter to this brief",
      "is_individual": true
    }
  ],
  "edges": [
    {
      "source": "exact name of source node",
      "target": "exact name of target node",
      "type": "EDGE_TYPE_NAME from the ontology",
      "description": "one short phrase about the relationship"
    }
  ]
}

Rules:
- Generate AT LEAST 12 entities and AT LEAST 15 relationships if the brief is non-trivial
- Generate AT MOST 40 entities and AT MOST 60 relationships
- Every node "type" must exactly match one of the ontology entity_types names
- Every edge "type" must exactly match one of the ontology edge_types names
- Every edge "source" and "target" must exactly match a node "name" in this same response
- Be diverse: include people, organizations, publications, government bodies, communities — anything the ontology supports
- Output ONLY the JSON object, no markdown, no commentary
"""


GRAPH_EXTRACTION_USER = """RESEARCH BRIEF:
{brief}

CONTEXT:
{context}

ONTOLOGY:
Entity types ({n_entity}):
{entity_lines}

Edge types ({n_edge}):
{edge_lines}

Extract the graph for this brief. Output the JSON object only.
"""


def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def _looks_truncated(text: str) -> bool:
    """Heuristic: response is probably cut off mid-output.

    Reasoning models on Azure (Kimi K2.5 in particular) sometimes burn
    their token budget on chain-of-thought before they finish writing the
    JSON. The response starts well but ends mid-string or mid-object.
    """
    if not text:
        return False
    s = text.strip()
    if not s:
        return False
    # Looks like it should be JSON…
    if not s.startswith("{") and not s.startswith("["):
        return False
    # …but the brace/bracket counts don't balance
    open_braces = s.count("{")
    close_braces = s.count("}")
    open_brackets = s.count("[")
    close_brackets = s.count("]")
    if open_braces > close_braces:
        return True
    if open_brackets > close_brackets:
        return True
    # Or it doesn't end with a closing brace/bracket
    last = s[-1]
    if last not in "}]":
        return True
    return False


def _attempt_close_truncated_json(text: str) -> str:
    """Best-effort repair of a truncated JSON response.

    Strategy:
      1. Find the last complete `}` (the last full object boundary)
      2. Walk back from that point, balancing brackets and braces
      3. If we land inside a `nodes`/`edges` array, close it
      4. Otherwise just append closers until balanced

    The result will still be parseable JSON containing as many of the
    completed entities as possible.
    """
    if not text:
        return text
    s = text.strip()

    # Find the last `},` or `}` that's followed by either `,` or just whitespace
    # then end-of-string. That's our likely "last complete object" boundary.
    last_complete = -1
    in_string = False
    escape = False
    for i, ch in enumerate(s):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "}":
            last_complete = i
    if last_complete == -1:
        return s

    # Truncate to the last complete object, then balance the wrapping arrays/objects
    truncated = s[: last_complete + 1]

    # Strip a trailing partial entry like `, { "name": "P` if present
    truncated = re.sub(r",\s*\{[^}]*$", "", truncated)

    # Count outstanding opens
    in_string = False
    escape = False
    open_braces = 0
    open_brackets = 0
    for ch in truncated:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            open_braces += 1
        elif ch == "}":
            open_braces -= 1
        elif ch == "[":
            open_brackets += 1
        elif ch == "]":
            open_brackets -= 1

    # Append closers — brackets first (innermost), then braces
    repaired = truncated
    repaired += "]" * max(0, open_brackets)
    repaired += "}" * max(0, open_braces)
    return repaired


def _parse_graph_json(raw: str) -> Optional[dict]:
    """Parse the LLM's JSON output, repairing common truncation patterns.

    Order of attempts:
      1. Direct parse after markdown fence stripping
      2. Extract first {...} block via regex
      3. Repair truncated output and re-parse
    """
    cleaned = _strip_markdown_fences(raw)

    # Attempt 1: direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Attempt 2: extract the first {...} block
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Attempt 3: repair truncated JSON if it looks cut off
    if _looks_truncated(cleaned):
        repaired = _attempt_close_truncated_json(cleaned)
        try:
            parsed = json.loads(repaired)
            logger.info(
                "Recovered truncated graph JSON: %d nodes after repair",
                len(parsed.get("nodes", [])) if isinstance(parsed, dict) else 0,
            )
            return parsed
        except json.JSONDecodeError as exc:
            logger.warning("JSON repair attempt failed: %s", exc)

    return None


class InMemoryGraphBuilder:
    """LLM-driven, single-pass graph extraction. No external services."""

    async def build(
        self,
        brief: str,
        ontology: Ontology,
        context: str = "",
    ) -> Optional[KnowledgeGraph]:
        if not brief or not brief.strip() or not ontology.entity_types:
            return None

        # Pre-build a lookup for ontology validation
        entity_type_index = {e.name.lower(): e for e in ontology.entity_types}
        edge_type_index = {e.name.lower(): e for e in ontology.edge_types}

        entity_lines = "\n".join(
            f"- {e.name}: {e.description}" for e in ontology.entity_types
        )
        edge_lines = "\n".join(
            f"- {e.name}: {e.description}" for e in ontology.edge_types
        )

        user_message = GRAPH_EXTRACTION_USER.format(
            brief=brief.strip(),
            context=(context or "No additional context provided.").strip(),
            n_entity=len(ontology.entity_types),
            n_edge=len(ontology.edge_types),
            entity_lines=entity_lines,
            edge_lines=edge_lines,
        )

        # ============================================
        # LLM call with auto-retry on truncated JSON
        # ============================================
        #
        # Graph extraction is the heaviest single LLM call (12-40 nodes +
        # 15-60 edges of JSON). Reasoning models like Kimi K2.5 can burn
        # their token budget on chain-of-thought before they finish writing
        # the JSON. We retry with progressively larger budgets if we detect
        # truncation, and parse with best-effort repair as a last resort.
        budgets = [6000, 9000, 12000]
        llm = get_llm()
        parsed: Optional[dict] = None
        last_raw: str = ""

        for attempt, budget in enumerate(budgets, 1):
            try:
                raw = await llm.generate(
                    system=GRAPH_EXTRACTION_PROMPT,
                    user_message=user_message,
                    max_tokens=budget,
                )
            except Exception as exc:
                logger.warning(
                    "Graph extraction LLM call failed (attempt %d/%d): %s",
                    attempt, len(budgets), exc,
                )
                continue

            if not raw or not raw.strip():
                logger.warning(
                    "Graph extraction returned empty (attempt %d/%d)",
                    attempt, len(budgets),
                )
                continue

            last_raw = raw
            parsed = _parse_graph_json(raw)
            if parsed and isinstance(parsed, dict) and parsed.get("nodes"):
                if attempt > 1:
                    logger.info(
                        "Graph extraction recovered on attempt %d (budget %d)",
                        attempt, budget,
                    )
                break

            # Parsing failed — was it truncation?
            if _looks_truncated(raw) and attempt < len(budgets):
                logger.warning(
                    "Graph JSON looks truncated (attempt %d/%d, budget %d). "
                    "Retrying with budget %d.",
                    attempt, len(budgets), budget, budgets[attempt],
                )
                continue

            # Not truncated, just unparseable — give up
            break

        if not parsed or not isinstance(parsed, dict):
            logger.warning(
                "Could not parse graph JSON after %d attempts. Raw start: %s",
                len(budgets), (last_raw or "")[:200],
            )
            return None

        raw_nodes = parsed.get("nodes") or []
        raw_edges = parsed.get("edges") or []
        if not isinstance(raw_nodes, list) or not isinstance(raw_edges, list):
            return None

        # Build nodes, validating types against the ontology
        nodes_by_name: dict[str, GraphEntityNode] = {}
        for item in raw_nodes:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            type_name = str(item.get("type") or "").strip()
            if not name or not type_name:
                continue
            if type_name.lower() not in entity_type_index:
                # Coerce unknown types to the closest fallback
                type_name = "Person" if item.get("is_individual", True) else "Organization"
                if type_name.lower() not in entity_type_index:
                    continue
            ontology_type = entity_type_index[type_name.lower()]
            node = GraphEntityNode(
                id=make_entity_id(),
                name=name,
                type=ontology_type.name,
                description=str(item.get("description") or "").strip(),
                attributes={},
                is_individual=bool(item.get("is_individual", ontology_type.is_individual)),
            )
            # Dedupe by lowercased name
            key = name.lower()
            if key not in nodes_by_name:
                nodes_by_name[key] = node

        nodes = list(nodes_by_name.values())
        if not nodes:
            return None

        # Build edges, validating types and resolving source/target by name
        edges: list[GraphRelationEdge] = []
        for item in raw_edges:
            if not isinstance(item, dict):
                continue
            src_name = str(item.get("source") or "").strip().lower()
            tgt_name = str(item.get("target") or "").strip().lower()
            type_name = str(item.get("type") or "").strip()
            if not src_name or not tgt_name or not type_name:
                continue
            if src_name not in nodes_by_name or tgt_name not in nodes_by_name:
                continue
            if type_name.lower() not in edge_type_index:
                # Pick the first edge type as fallback rather than dropping
                if not ontology.edge_types:
                    continue
                type_name = ontology.edge_types[0].name
            ontology_edge = edge_type_index.get(type_name.lower()) or ontology.edge_types[0]
            edges.append(
                GraphRelationEdge(
                    id=make_edge_id(),
                    source_id=nodes_by_name[src_name].id,
                    target_id=nodes_by_name[tgt_name].id,
                    type=ontology_edge.name,
                    description=str(item.get("description") or "").strip(),
                    strength=0.7,
                )
            )

        return KnowledgeGraph(nodes=nodes, edges=edges)
