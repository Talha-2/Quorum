"""
Environment setup — generate one agent per entity in the knowledge graph.
"""

from __future__ import annotations

import json
import logging
import random
import re
from typing import List, Optional

from quorum_backend.llm import get_llm

from quorum_backend.pipeline.models import AgentProfile, GraphEntityNode, KnowledgeGraph, make_agent_id

logger = logging.getLogger(__name__)


PERSONA_BATCH_PROMPT = """You are a persona designer for a scholarly multi-agent reasoning simulation.

You will be given a research brief and a batch of REAL-WORLD ENTITIES extracted
from that brief. For each entity, design a rich agent profile representing how
that entity would speak and behave in a debate about the brief.

Return ONLY a JSON array. Each element corresponds to one entity in the same
order as the input. Required fields per entity:

[
  {
    "role": "short job title or archetype, e.g. 'Constitutional Historian' or 'Senior Investigative Reporter'",
    "bio": "200-character social-media-style bio that describes who they are",
    "persona": "1500-2000 character long-form persona that MUST include these labelled sections in order. Do NOT use real newlines inside the value — use the literal sequence \\n\\n between sections:\\n\\nBackground: 2-3 sentences about who this entity is, their experience, and why they care about the brief.\\n\\nBehavior Profile: 2-3 sentences about their argumentation style, what kind of language they use, what they sound like in a debate.\\n\\nUnique Memory: 2-3 sentences about a specific experience or precedent they would reference when arguing about this brief.\\n\\nSocial Network: 2-3 sentences about their allies, opponents, audience, or institutional ties — who they listen to and who listens to them.",
    "expertise": ["3-5 short keywords describing their domain expertise"],
    "interested_topics": ["2-4 short keywords from the brief that they would track"],
    "age": <integer age, or 30 for organizations>,
    "gender": "male" | "female" | "other",
    "mbti": "<one of the 16 MBTI types, e.g. INTJ, ENFP>",
    "country": "<country in English, e.g. United States, China, Germany>",
    "profession": "<short profession descriptor>",
    "optimism": <float 0.0-1.0>,
    "risk_tolerance": <float 0.0-1.0>,
    "caution": <float 0.0-1.0>,
    "stance": "support" | "oppose" | "neutral",
    "bias": "one short phrase describing this entity's primary bias on this question"
  }
]

Rules:
- Return EXACTLY {n} objects in the same order as the input entities
- For organizations / groups / institutions: age=30, gender="other", MBTI describes account style (e.g. ISTJ for rigorous-conservative)
- Make stances diverse — some entities should support, some oppose, some be neutral
- Personality numbers must be between 0.0 and 1.0
- All string values must be valid JSON strings — escape internal quotes, use \\n\\n between persona sections
- Output ONLY the JSON array, no markdown, no commentary
"""


PERSONA_BATCH_USER = """RESEARCH BRIEF:
{brief}

ENTITIES (in order):
{entity_lines}

Output the JSON array of {n} persona objects.
"""


def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def _parse_persona_array(raw: str) -> Optional[list]:
    cleaned = _strip_markdown_fences(raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\[\s*\{[\s\S]*\}\s*\]", cleaned)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def _slugify_username(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]", "", name.lower())[:18]
    if not slug:
        slug = "agent"
    suffix = random.randint(100, 999)
    return f"{slug}_{suffix}"


def _coerce_float(value, default: float = 0.5) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, f))


VALID_MBTI = frozenset(
    (
        "INTJ",
        "INTP",
        "ENTJ",
        "ENTP",
        "INFJ",
        "INFP",
        "ENFJ",
        "ENFP",
        "ISTJ",
        "ISFJ",
        "ESTJ",
        "ESFJ",
        "ISTP",
        "ISFP",
        "ESTP",
        "ESFP",
    )
)


def _coerce_age(value, is_individual: bool) -> int:
    if not is_individual:
        return 30
    try:
        v = int(value)
    except (TypeError, ValueError):
        return random.randint(28, 55)
    return max(18, min(v, 95))


def _coerce_gender(value, is_individual: bool) -> str:
    if not is_individual:
        return "other"
    g = str(value or "").strip().lower()
    if g in ("male", "female", "other"):
        return g
    return random.choice(["male", "female"])


def _coerce_mbti(value, is_individual: bool) -> str:
    g = str(value or "").strip().upper()
    if g in VALID_MBTI:
        return g
    return "ISTJ" if not is_individual else random.choice(list(VALID_MBTI))


def _persona_dict_to_profile(persona: dict, entity: GraphEntityNode) -> AgentProfile:
    role = str(persona.get("role") or entity.type).strip()
    bio = str(persona.get("bio") or "").strip()
    persona_text = str(persona.get("persona") or "").strip()
    persona_text = persona_text.replace("\\n\\n", "\n\n").replace("\\n", "\n")

    expertise_raw = persona.get("expertise") or []
    if isinstance(expertise_raw, str):
        expertise_raw = [e.strip() for e in expertise_raw.split(",")]
    expertise = [str(e).strip() for e in expertise_raw if str(e).strip()][:6]

    interested_raw = persona.get("interested_topics") or []
    if isinstance(interested_raw, str):
        interested_raw = [t.strip() for t in interested_raw.split(",")]
    interested = [str(t).strip() for t in interested_raw if str(t).strip()][:6]

    stance = str(persona.get("stance") or "neutral").strip().lower()
    if stance not in {"support", "oppose", "neutral"}:
        stance = "neutral"

    return AgentProfile(
        id=make_agent_id(),
        user_name=_slugify_username(entity.name),
        name=entity.name,
        role=role,
        bio=bio or f"{role} concerned with this brief",
        persona=persona_text or f"{role} who would weigh in on this brief from a {stance} angle",
        expertise=expertise or [entity.type.lower()],
        interested_topics=interested,
        optimism=_coerce_float(persona.get("optimism"), 0.5),
        risk_tolerance=_coerce_float(persona.get("risk_tolerance"), 0.5),
        caution=_coerce_float(persona.get("caution"), 0.5),
        stance=stance,
        bias=str(persona.get("bias") or "").strip(),
        age=_coerce_age(persona.get("age"), entity.is_individual),
        gender=_coerce_gender(persona.get("gender"), entity.is_individual),
        mbti=_coerce_mbti(persona.get("mbti"), entity.is_individual),
        country=str(persona.get("country") or "").strip() or None,
        profession=str(persona.get("profession") or role).strip() or role,
        source_entity_id=entity.id,
        source_entity_type=entity.type,
        is_individual=entity.is_individual,
    )


def _fallback_profile(entity: GraphEntityNode) -> AgentProfile:
    return AgentProfile(
        id=make_agent_id(),
        user_name=_slugify_username(entity.name),
        name=entity.name,
        role=entity.type,
        bio=entity.description or f"A {entity.type.lower()}",
        persona=(
            f"Background: {entity.name} is a {entity.type.lower()} relevant to this brief.\n\n"
            "Behavior Profile: Speaks plainly, references concrete facts.\n\n"
            "Unique Memory: Cites their direct experience with the question at hand.\n\n"
            "Social Network: Connected to other entities in the same domain."
        ),
        expertise=[entity.type.lower()],
        interested_topics=[],
        optimism=0.5,
        risk_tolerance=0.5,
        caution=0.5,
        stance="neutral",
        bias="",
        age=30 if not entity.is_individual else random.randint(30, 55),
        gender="other" if not entity.is_individual else random.choice(["male", "female"]),
        mbti="ISTJ" if not entity.is_individual else random.choice(list(VALID_MBTI)),
        country=None,
        profession=entity.type,
        source_entity_id=entity.id,
        source_entity_type=entity.type,
        is_individual=entity.is_individual,
    )


SPEAKER_TYPE_PATTERNS = frozenset(
    (
        "person",
        "people",
        "individual",
        "figure",
        "speaker",
        "actor",
        "official",
        "leader",
        "expert",
        "scholar",
        "academic",
        "journalist",
        "witness",
        "survivor",
        "advocate",
        "critic",
        "analyst",
        "maker",
        "owner",
        "holder",
        "manager",
        "director",
        "founder",
        "chief",
        "head",
        "secretary",
        "minister",
        "judge",
        "writer",
        "researcher",
        "operator",
        "engineer",
        "designer",
        "artist",
        "organization",
        "organisation",
        "institution",
        "agency",
        "group",
        "community",
        "company",
        "firm",
        "corporation",
        "association",
        "outlet",
        "publisher",
        "newsroom",
        "press",
        "committee",
        "union",
        "party",
        "council",
        "tribunal",
        "court",
        "university",
        "school",
        "department",
        "ministry",
        "government",
        "ngo",
        "foundation",
        "movement",
        "coalition",
        "alliance",
        "stakeholder",
        "investor",
        "nation",
        "state",
        "republic",
    )
)

NON_SPEAKER_TYPE_PATTERNS = frozenset(
    (
        "event",
        "incident",
        "operation",
        "action",
        "attack",
        "war",
        "battle",
        "campaign",
        "bombing",
        "massacre",
        "atrocity",
        "crisis",
        "evidence",
        "document",
        "record",
        "post",
        "claim",
        "statement",
        "announcement",
        "speech",
        "ideology",
        "belief",
        "doctrine",
        "theory",
        "concept",
        "framework",
        "policy",
        "law",
        "rule",
        "regulation",
        "decision",
        "ruling",
        "judgment",
        "judgement",
        "verdict",
        "evaluation",
        "analysis",
        "trend",
        "pattern",
        "metric",
        "indicator",
        "measure",
        "platform",
        "channel",
        "medium",
        "technology",
        "place",
        "location",
        "site",
        "region",
        "city",
        "country",
        "date",
        "period",
        "era",
        "moment",
    )
)


def _tokenize_type(type_name: str) -> list[str]:
    spaced = re.sub(r"([A-Z])", r" \1", type_name or "")
    return re.findall(r"[a-z]+", spaced.lower())


def _is_speaker_capable(entity_type: str, is_individual: bool) -> bool:
    tokens = _tokenize_type(entity_type)
    if not tokens:
        return bool(is_individual)

    head = tokens[-1]
    if head in SPEAKER_TYPE_PATTERNS:
        return True
    if head in NON_SPEAKER_TYPE_PATTERNS:
        return False

    token_set = set(tokens)
    if token_set & SPEAKER_TYPE_PATTERNS:
        return True
    if token_set & NON_SPEAKER_TYPE_PATTERNS:
        return False

    return bool(is_individual)


async def generate_agents_for_graph(
    brief: str,
    graph: KnowledgeGraph,
    max_agents: int = 12,
    batch_size: int = 8,
) -> List[AgentProfile]:
    if not graph or not graph.nodes:
        return []

    speaker_nodes = [n for n in graph.nodes if _is_speaker_capable(n.type, n.is_individual)]
    if not speaker_nodes:
        speaker_nodes = [n for n in graph.nodes if n.is_individual] or list(graph.nodes)

    logger.info("Speaker filter: %d/%d nodes are speaker-capable", len(speaker_nodes), len(graph.nodes))

    speaker_ids = {n.id for n in speaker_nodes}
    degree: dict[str, int] = {n.id: 0 for n in speaker_nodes}
    for e in graph.edges:
        if e.source_id in speaker_ids:
            degree[e.source_id] = degree.get(e.source_id, 0) + 1
        if e.target_id in speaker_ids:
            degree[e.target_id] = degree.get(e.target_id, 0) + 1

    sorted_nodes = sorted(speaker_nodes, key=lambda n: degree.get(n.id, 0), reverse=True)
    selected = sorted_nodes[:max_agents]

    agents: List[AgentProfile] = []

    for batch_start in range(0, len(selected), batch_size):
        batch = selected[batch_start : batch_start + batch_size]
        if not batch:
            continue

        entity_lines = "\n".join(
            f"{i + 1}. {e.name} ({e.type}) — {e.description or 'no description'}"
            for i, e in enumerate(batch)
        )
        user_message = PERSONA_BATCH_USER.format(
            brief=brief.strip(),
            entity_lines=entity_lines,
            n=len(batch),
        )
        # PERSONA_BATCH_PROMPT embeds a literal JSON example, so str.format()
        # would misread its braces. {n} is the only real placeholder.
        system = PERSONA_BATCH_PROMPT.replace("{n}", str(len(batch)))

        try:
            llm = get_llm()
            raw = await llm.generate(system=system, user_message=user_message, max_tokens=3500)
        except Exception as exc:
            logger.warning("Persona batch LLM call failed: %s", exc)
            agents.extend(_fallback_profile(e) for e in batch)
            continue

        parsed = _parse_persona_array(raw or "")
        if not parsed or not isinstance(parsed, list):
            logger.warning("Could not parse persona batch JSON.")
            agents.extend(_fallback_profile(e) for e in batch)
            continue

        for i, entity in enumerate(batch):
            persona = parsed[i] if i < len(parsed) and isinstance(parsed[i], dict) else None
            if persona is None:
                agents.append(_fallback_profile(entity))
            else:
                try:
                    agents.append(_persona_dict_to_profile(persona, entity))
                except Exception as exc:  # pragma: no cover
                    logger.warning("Bad persona for %s: %s", entity.name, exc)
                    agents.append(_fallback_profile(entity))

    return agents

