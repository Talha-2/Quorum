"""
Dynamic persona generation.

Instead of using hardcoded archetypes (Risk Radar, Opportunity Scout, etc.) for
every topic, this module asks the LLM to design a custom panel of expert agents
tailored to the specific brief the user submitted. Each persona has a unique
name, background, expertise, personality, and bias relevant to the topic.

For a question about WW2 history, you'll get historians and ethicists.
For a question about a startup decision, you'll get a VC, a founder, an operator.
For a question about a medical treatment, you'll get clinicians and a patient
advocate.

If LLM generation fails (provider down, malformed output, etc.) the caller can
fall back to the static templates in `generic.py`.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Dict, List, Optional

try:
    from ..core.types import AgentArchetype, AgentPersonality
    from ..llm import get_llm
except ImportError:  # pragma: no cover - supports direct script execution
    from core.types import AgentArchetype, AgentPersonality
    from llm import get_llm

logger = logging.getLogger(__name__)


PERSONA_GENERATION_PROMPT = """You are designing a panel of expert agents who will debate a question.

QUESTION:
{brief}

CONTEXT:
{context}

Design EXACTLY {count} distinct expert personas who would have meaningful and \
**conflicting** perspectives on this question. They should be diverse in:
- Background (academic, industry, practitioner, critic, advocate, etc.)
- Stance (some likely to favor action, some likely to oppose, some neutral)
- Methodology (data-driven, historical, ethical, intuitive, lived experience, \
quantitative, qualitative, etc.)
- Discipline (mix specialties — don't make them all the same kind of expert)

For each persona return JSON with these fields:
  "name": short distinctive name (e.g. "Dr. Helena Marsh", "The Field Operator", \
"Nadia, ICU Nurse")
  "role": short job title or archetype (e.g. "Constitutional Historian", \
"Series-A Founder", "Compliance Officer")
  "background": one-sentence credibility line explaining who they are and why \
they'd care about this question
  "expertise": array of 3-5 short keywords
  "personality": object with three numbers from 0.0 to 1.0:
      "optimism" — 0=pessimistic, 1=optimistic
      "risk_tolerance" — 0=risk-averse, 1=risk-seeking
      "caution" — 0=bold, 1=cautious
  "bias": one short phrase describing their primary bias toward the question \
(e.g. "favors precedent over novelty", "skeptical of state power")
  "stance": one of "support", "oppose", "neutral"

Output ONLY a valid JSON array of {count} persona objects. No prose, no \
markdown fences, no commentary. Start your response with [ and end with ].
"""


def _strip_markdown_fences(text: str) -> str:
    """Strip ```json … ``` fences if the LLM wrapped its output."""
    text = text.strip()
    if text.startswith("```"):
        # Remove opening fence and language tag
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def _coerce_float(value, default: float = 0.5) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, f))


def _persona_to_archetype(persona: Dict, index: int) -> AgentArchetype:
    """Convert a single LLM-generated persona dict into an AgentArchetype."""
    name = str(persona.get("name") or f"Expert {index + 1}").strip()
    role = str(persona.get("role") or "Expert").strip()
    background = str(persona.get("background") or "").strip()
    bias = str(persona.get("bias") or "").strip()
    stance = str(persona.get("stance") or "neutral").strip().lower()

    expertise_raw = persona.get("expertise") or []
    if isinstance(expertise_raw, str):
        expertise_raw = [e.strip() for e in expertise_raw.split(",")]
    expertise = [str(e).strip() for e in expertise_raw if str(e).strip()][:6] or [role]

    personality_raw = persona.get("personality") or {}
    if not isinstance(personality_raw, dict):
        personality_raw = {}

    personality = AgentPersonality(
        optimism=_coerce_float(personality_raw.get("optimism"), 0.5),
        risk_tolerance=_coerce_float(personality_raw.get("risk_tolerance"), 0.5),
        caution=_coerce_float(personality_raw.get("caution"), 0.5),
        communication_style=str(persona.get("communication_style") or "balanced"),
        bias=bias or None,
    )

    description_parts = [role]
    if background:
        description_parts.append(background)
    description = ". ".join(description_parts)

    responsibilities = [
        f"Argue from the perspective of a {role.lower()}",
        f"Bring {expertise[0]} expertise to the discussion" if expertise else "Bring expertise",
        f"Hold a {stance} stance unless evidence shifts you",
    ]

    goals = [
        f"Help the group reach a defensible position on the question",
        f"Surface considerations that other experts may miss",
    ]

    constraints = []
    if bias:
        constraints.append(f"You acknowledge your bias: {bias}")

    return AgentArchetype(
        id=str(uuid.uuid4()),
        name=name,
        description=description,
        personality=personality,
        expertise=expertise,
        responsibilities=responsibilities,
        goals=goals,
        constraints=constraints,
    )


async def generate_dynamic_personas(
    brief: str,
    context: str = "",
    count: int = 6,
) -> Optional[List[AgentArchetype]]:
    """
    Ask the LLM to design a topic-specific panel of personas.

    Returns a list of AgentArchetype objects, or None if generation failed
    (so the caller can fall back to static templates).
    """
    if not brief or not brief.strip():
        logger.info("No brief provided; skipping dynamic persona generation.")
        return None

    count = max(2, min(int(count or 6), 12))

    prompt = PERSONA_GENERATION_PROMPT.format(
        brief=brief.strip(),
        context=(context or "No additional context.").strip(),
        count=count,
    )

    system = (
        "You are a panel designer. Your only job is to return a JSON array of "
        "expert persona objects in the exact schema requested. Do not include "
        "any text outside the JSON array."
    )

    try:
        llm = get_llm()
        raw = await llm.generate(system=system, user_message=prompt, max_tokens=2048)
    except Exception as exc:
        logger.warning("LLM persona generation call failed: %s", exc)
        return None

    if not raw or not raw.strip():
        logger.warning("LLM returned empty response for persona generation.")
        return None

    cleaned = _strip_markdown_fences(raw)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        # Some providers wrap things; try to find the first JSON array in the response
        match = re.search(r"\[\s*\{.*?\}\s*\]", cleaned, re.DOTALL)
        if not match:
            logger.warning("Could not parse persona JSON: %s. Raw: %s", exc, cleaned[:200])
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError as exc2:
            logger.warning("Could not parse extracted persona JSON: %s", exc2)
            return None

    if not isinstance(parsed, list) or not parsed:
        logger.warning("Parsed persona output is not a non-empty list: %r", parsed)
        return None

    archetypes: List[AgentArchetype] = []
    for index, persona in enumerate(parsed[:count]):
        if not isinstance(persona, dict):
            continue
        try:
            archetypes.append(_persona_to_archetype(persona, index))
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Skipping malformed persona at index %d: %s", index, exc)

    if len(archetypes) < 2:
        logger.warning("Got fewer than 2 valid personas; falling back to static templates.")
        return None

    logger.info("Generated %d dynamic personas for brief: %s",
                len(archetypes), brief[:80])
    return archetypes
