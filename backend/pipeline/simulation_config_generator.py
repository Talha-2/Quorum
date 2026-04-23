"""
Simulation config generator — Stage 03 of the pipeline.

Four sequential LLM calls to produce the full simulation configuration:

  1. Generate TimeSimulationConfig (1 LLM call)
  2. Generate EventConfig (1 LLM call) — narrative direction + hot topics + initial posts
  3. Generate AgentActivityConfig in batches (N LLM calls) — per-agent behavior
  4. Build two PlatformConfigs (Feed + Community) from constants
  5. Post-process: assign each initial post to a real agent_id by type-aliasing

Each step has its own LLM call, json parsing with `_parse_json_object`, content
filter detection (so the run continues with sensible defaults rather than 500s),
and a "reasoning" string captured into SimulationParameters.generation_reasoning.

This is the most robustness-critical part of the pipeline because any single
LLM failure shouldn't tank the whole run.
"""

from __future__ import annotations

import json
import logging
import math
import re
from typing import Any, Callable, Dict, List, Optional

try:
    from ..llm import get_llm, ContentFilterError
except ImportError:  # pragma: no cover
    from llm import get_llm, ContentFilterError

from .models import (
    AgentActivityConfig,
    AgentProfile,
    EventConfig,
    PlatformConfig,
    Project,
    SimulationParameters,
    TimeSimulationConfig,
)

logger = logging.getLogger(__name__)

# How many agents per LLM call when generating activity configs
AGENTS_PER_BATCH = 8
# Cap on context fed to each step's prompt
TIME_CONTEXT_CHARS = 8000
EVENT_CONTEXT_CHARS = 8000


# ============================================
# JSON parsing utility (shared across all 4 steps)
# ============================================

def _parse_json_object(raw: str) -> Optional[dict]:
    """Strip markdown fences and try hard to extract a valid JSON object."""
    if not raw:
        return None
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```\s*$", "", s)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", s)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def _coerce_int(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(v, hi))


def _coerce_float(value: Any, default: float, lo: float = 0.0, hi: float = 10.0) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return max(lo, min(v, hi))


def _coerce_int_list(value: Any, default: List[int]) -> List[int]:
    if not isinstance(value, list):
        return default
    out: List[int] = []
    for x in value:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
    return out or default


# ============================================
# Step 1 — Time config
# ============================================

TIME_CONFIG_SYSTEM_PROMPT = (
    "You are a social media simulation expert. Return ONLY a valid JSON object. "
    "The time configuration must reflect realistic activity rhythms for the audience "
    "implied by the simulation brief."
)

TIME_CONFIG_USER_TEMPLATE = """Based on this brief, design a time-of-day activity configuration for a multi-agent social simulation.

BRIEF:
{brief}

CONTEXT:
{context}

NUMBER OF AGENTS: {num_agents}

Design parameters that reflect when the audience implied by this brief is likely to be active. Defaults reflect a Chinese work-week (UTC+8) but you should adjust based on the brief — students peak at 21-23, media is all-day, officials only work hours, breaking-news topics may have all-night discussion.

Return ONLY this JSON object — no markdown, no commentary:
{{
  "total_simulation_hours": <int 24-168>,
  "minutes_per_round": <int 30-120>,
  "agents_per_hour_min": <int 1-{max_agents}>,
  "agents_per_hour_max": <int 1-{max_agents}>,
  "peak_hours": <int array, hour-of-day 0-23>,
  "off_peak_hours": <int array>,
  "morning_hours": <int array>,
  "work_hours": <int array>,
  "reasoning": "<one-paragraph rationale for these choices>"
}}
"""


async def _generate_time_config(
    brief: str,
    context: str,
    num_agents: int,
) -> tuple[TimeSimulationConfig, str]:
    """Step 1 — generate the time config. Returns (config, reasoning)."""
    max_agents_allowed = max(1, int(num_agents * 0.9))
    user = TIME_CONFIG_USER_TEMPLATE.format(
        brief=brief.strip(),
        context=(context or "No additional context.")[:TIME_CONTEXT_CHARS],
        num_agents=num_agents,
        max_agents=max_agents_allowed,
    )

    parsed: Optional[dict] = None
    try:
        llm = get_llm()
        raw = await llm.generate(
            system=TIME_CONFIG_SYSTEM_PROMPT,
            user_message=user,
            max_tokens=1500,
        )
        parsed = _parse_json_object(raw)
    except ContentFilterError:
        logger.warning("Time config generation blocked by content filter; using defaults")
    except Exception as exc:
        logger.warning("Time config LLM call failed: %s; using defaults", exc)

    if parsed is None:
        config = TimeSimulationConfig(
            agents_per_hour_min=max(1, num_agents // 12),
            agents_per_hour_max=max(2, num_agents // 4),
        )
        reason = "Defaults used (LLM unavailable)"
        return config, reason

    config = TimeSimulationConfig(
        total_simulation_hours=_coerce_int(parsed.get("total_simulation_hours"), 72, 24, 168),
        minutes_per_round=_coerce_int(parsed.get("minutes_per_round"), 60, 30, 120),
        agents_per_hour_min=_coerce_int(parsed.get("agents_per_hour_min"), max(1, num_agents // 12), 1, max_agents_allowed),
        agents_per_hour_max=_coerce_int(parsed.get("agents_per_hour_max"), max(2, num_agents // 4), 1, max_agents_allowed),
        peak_hours=_coerce_int_list(parsed.get("peak_hours"), [19, 20, 21, 22]),
        off_peak_hours=_coerce_int_list(parsed.get("off_peak_hours"), [0, 1, 2, 3, 4, 5]),
        morning_hours=_coerce_int_list(parsed.get("morning_hours"), [6, 7, 8]),
        work_hours=_coerce_int_list(parsed.get("work_hours"), list(range(9, 19))),
    )
    # Sanity check: min < max
    if config.agents_per_hour_min >= config.agents_per_hour_max:
        config.agents_per_hour_min = max(1, config.agents_per_hour_max // 2)

    reasoning = str(parsed.get("reasoning") or "Time configuration generated").strip()
    return config, reasoning


# ============================================
# Step 2 — Event config (narrative + hot topics + initial posts)
# ============================================

EVENT_CONFIG_SYSTEM_PROMPT = (
    "You are a public-opinion analyst. Return ONLY a valid JSON object. "
    "The 'poster_type' field for each initial post MUST be in PascalCase and "
    "match one of the available entity types exactly so the post can be assigned "
    "to a real agent."
)

EVENT_CONFIG_USER_TEMPLATE = """Based on this brief, design the initial event configuration for a multi-agent social simulation about it.

BRIEF:
{brief}

CONTEXT:
{context}

AVAILABLE ENTITY TYPES (with example entities):
{type_info}

You will produce:
- hot_topics: 4-6 short hashtag-style keywords drawn from the brief
- narrative_direction: a 2-3 sentence description of how public opinion will likely evolve
- initial_posts: 3-6 starter posts that seed the simulation. Each post needs:
    - content: 1-3 sentences in the voice of a {{poster_type}}-style account
    - poster_type: must be one of the available entity types above (PascalCase)

Return ONLY this JSON object — no markdown, no commentary:
{{
  "hot_topics": ["topic1", "topic2", ...],
  "narrative_direction": "<2-3 sentence description>",
  "initial_posts": [
    {{ "content": "<post content>", "poster_type": "<EntityType>" }},
    ...
  ],
  "reasoning": "<one-paragraph rationale>"
}}
"""


async def _generate_event_config(
    brief: str,
    context: str,
    agent_profiles: List[AgentProfile],
) -> tuple[EventConfig, str]:
    """Step 2 — generate narrative + hot topics + initial posts."""
    # Build entity type histogram with example names
    type_examples: Dict[str, List[str]] = {}
    for a in agent_profiles:
        t = a.source_entity_type or a.role or "Person"
        type_examples.setdefault(t, [])
        if len(type_examples[t]) < 3:
            type_examples[t].append(a.name)

    type_info = "\n".join(
        f"- {t}: {', '.join(names)}" for t, names in type_examples.items()
    )

    user = EVENT_CONFIG_USER_TEMPLATE.format(
        brief=brief.strip(),
        context=(context or "No additional context.")[:EVENT_CONTEXT_CHARS],
        type_info=type_info or "(no entity types available)",
    )

    parsed: Optional[dict] = None
    try:
        llm = get_llm()
        raw = await llm.generate(
            system=EVENT_CONFIG_SYSTEM_PROMPT,
            user_message=user,
            max_tokens=2000,
        )
        parsed = _parse_json_object(raw)
    except ContentFilterError:
        logger.warning("Event config generation blocked by content filter; using minimal default")
    except Exception as exc:
        logger.warning("Event config LLM call failed: %s; using minimal default", exc)

    if parsed is None:
        return EventConfig(
            hot_topics=[],
            narrative_direction=f"Discussion of: {brief[:200]}",
            initial_posts=[],
        ), "Defaults used (LLM unavailable)"

    hot_topics_raw = parsed.get("hot_topics") or []
    hot_topics = [str(t).strip() for t in hot_topics_raw if str(t).strip()][:8]

    initial_posts_raw = parsed.get("initial_posts") or []
    initial_posts: List[Dict[str, Any]] = []
    for p in initial_posts_raw[:8]:
        if not isinstance(p, dict):
            continue
        content = str(p.get("content") or "").strip()
        poster_type = str(p.get("poster_type") or "").strip()
        if not content:
            continue
        initial_posts.append({
            "content": content,
            "poster_type": poster_type,
            "poster_agent_id": None,  # filled in by post-processor
        })

    config = EventConfig(
        initial_posts=initial_posts,
        hot_topics=hot_topics,
        narrative_direction=str(parsed.get("narrative_direction") or "").strip(),
    )
    reasoning = str(parsed.get("reasoning") or "Event configuration generated").strip()
    return config, reasoning


# ============================================
# Step 2.5 — Type-alias matching for initial post → agent
# ============================================

TYPE_ALIASES: Dict[str, List[str]] = {
    "official": ["official", "university", "governmentagency", "government", "agency"],
    "university": ["university", "institution", "school", "academic"],
    "mediaoutlet": ["mediaoutlet", "media", "newsoutlet", "publication", "press", "journalist"],
    "newsarticle": ["mediaoutlet", "media", "publication"],
    "student": ["student", "alumni", "person"],
    "professor": ["professor", "expert", "scholar", "academic"],
    "alumni": ["alumni", "person", "student"],
    "organization": ["organization", "ngo", "foundation", "company", "group"],
    "person": ["person", "individual", "publicfigure"],
    "publicfigure": ["publicfigure", "person", "expert"],
    "stakeholder": ["stakeholder", "stakeholdergroup", "group"],
    "historicalfigure": ["historicalfigure", "person", "publicfigure"],
    "nationstate": ["nationstate", "government", "state"],
}


def _assign_initial_post_agents(
    event_config: EventConfig,
    agent_configs: List[AgentActivityConfig],
) -> EventConfig:
    """Match each post's poster_type against real agents using the alias table.

    No LLM call — pure deterministic post-processor.
    """
    if not event_config.initial_posts or not agent_configs:
        return event_config

    by_type: Dict[str, List[AgentActivityConfig]] = {}
    for a in agent_configs:
        key = (a.entity_type or "").lower()
        by_type.setdefault(key, []).append(a)

    used_index: Dict[str, int] = {}

    def _pick_from(type_key: str) -> Optional[int]:
        bucket = by_type.get(type_key)
        if not bucket:
            return None
        idx = used_index.get(type_key, 0) % len(bucket)
        used_index[type_key] = idx + 1
        return bucket[idx].agent_id

    updated: List[Dict[str, Any]] = []
    for post in event_config.initial_posts:
        poster_type = (post.get("poster_type") or "").lower()
        agent_id: Optional[int] = None

        # 1. Direct match
        agent_id = _pick_from(poster_type)

        # 2. Alias match
        if agent_id is None:
            for alias_key, aliases in TYPE_ALIASES.items():
                if poster_type in aliases or poster_type == alias_key:
                    for alias in aliases:
                        agent_id = _pick_from(alias)
                        if agent_id is not None:
                            break
                if agent_id is not None:
                    break

        # 3. Fallback: highest-influence agent
        if agent_id is None and agent_configs:
            best = max(agent_configs, key=lambda a: a.influence_weight)
            agent_id = best.agent_id

        updated.append({
            "content": post.get("content", ""),
            "poster_type": post.get("poster_type", "Unknown"),
            "poster_agent_id": agent_id,
        })

    event_config.initial_posts = updated
    return event_config


# ============================================
# Step 3 — Per-agent activity configs (in batches)
# ============================================

AGENT_BATCH_SYSTEM_PROMPT = (
    "You are a social media behavior analyst. Return ONLY a valid JSON object. "
    "Each agent_id must match the input exactly."
)

AGENT_BATCH_USER_TEMPLATE = """Generate per-agent activity profiles for this batch of {n} agents in a social media simulation.

BRIEF: {brief}

AGENTS (in order, with stable agent_id):
```json
{agent_list}
```

Tuning guide (rough — adjust based on the brief and entity type):
- Officials / Universities / Government: activity_level 0.1-0.3, work hours [9-17], slow response 60-240min, high influence 2.5-3.0
- Media outlets / News: activity_level 0.4-0.6, all-day [8-23], fast response 5-30min, high influence 2.0-2.5
- Individuals / Students / Alumni: activity_level 0.6-0.9, evening [18-23], fast 1-15min, low influence 0.8-1.2
- Public figures / Experts: activity_level 0.4-0.6, mixed hours, mid-high influence 1.5-2.0

Return ONLY this JSON object — no markdown, no commentary:
{{
  "agent_configs": [
    {{
      "agent_id": <int matching input>,
      "activity_level": <0.0-1.0>,
      "posts_per_hour": <0.0-10.0>,
      "comments_per_hour": <0.0-20.0>,
      "active_hours": <int array, 0-23>,
      "response_delay_min": <int minutes>,
      "response_delay_max": <int minutes>,
      "sentiment_bias": <-1.0 to 1.0>,
      "stance": "supportive" | "opposing" | "neutral" | "observer",
      "influence_weight": <0.0-3.0>
    }}
  ]
}}
"""


def _build_agent_batch_input(
    agents: List[AgentProfile],
    start_idx: int,
) -> tuple[List[Dict[str, Any]], List[AgentProfile]]:
    """Convert AgentProfile slice into a JSON-serializable batch payload."""
    payload: List[Dict[str, Any]] = []
    for offset, a in enumerate(agents):
        payload.append({
            "agent_id": start_idx + offset,
            "entity_name": a.name,
            "entity_type": a.source_entity_type or a.role or "Person",
            "summary": (a.bio or a.persona or "")[:200],
            "stance_hint": a.stance,
        })
    return payload, agents


async def _generate_agent_configs_batch(
    brief: str,
    agents: List[AgentProfile],
    start_idx: int,
) -> List[AgentActivityConfig]:
    """Generate AgentActivityConfig for a single batch of agents."""
    if not agents:
        return []

    batch_payload, _ = _build_agent_batch_input(agents, start_idx)
    user = AGENT_BATCH_USER_TEMPLATE.format(
        n=len(agents),
        brief=brief.strip(),
        agent_list=json.dumps(batch_payload, ensure_ascii=False, indent=2),
    )

    parsed: Optional[dict] = None
    try:
        llm = get_llm()
        raw = await llm.generate(
            system=AGENT_BATCH_SYSTEM_PROMPT,
            user_message=user,
            max_tokens=3500,
        )
        parsed = _parse_json_object(raw)
    except ContentFilterError:
        logger.warning("Agent batch generation blocked by content filter; using fallback")
    except Exception as exc:
        logger.warning("Agent batch LLM call failed: %s; using fallback", exc)

    if parsed is None:
        return [_fallback_agent_config(a, start_idx + i) for i, a in enumerate(agents)]

    raw_list = parsed.get("agent_configs") or []
    by_id = {int(c.get("agent_id", -1)): c for c in raw_list if isinstance(c, dict)}

    out: List[AgentActivityConfig] = []
    for offset, a in enumerate(agents):
        agent_id = start_idx + offset
        c = by_id.get(agent_id)
        if c is None:
            out.append(_fallback_agent_config(a, agent_id))
            continue
        out.append(AgentActivityConfig(
            agent_id=agent_id,
            entity_uuid=a.id,
            entity_name=a.name,
            entity_type=a.source_entity_type or a.role or "Person",
            activity_level=_coerce_float(c.get("activity_level"), 0.5, 0.0, 1.0),
            posts_per_hour=_coerce_float(c.get("posts_per_hour"), 1.0, 0.0, 10.0),
            comments_per_hour=_coerce_float(c.get("comments_per_hour"), 2.0, 0.0, 20.0),
            active_hours=_coerce_int_list(c.get("active_hours"), list(range(8, 23))),
            response_delay_min=_coerce_int(c.get("response_delay_min"), 5, 1, 600),
            response_delay_max=_coerce_int(c.get("response_delay_max"), 60, 1, 600),
            sentiment_bias=_coerce_float(c.get("sentiment_bias"), 0.0, -1.0, 1.0),
            stance=str(c.get("stance") or "neutral").lower(),
            influence_weight=_coerce_float(c.get("influence_weight"), 1.0, 0.0, 3.0),
        ))
    return out


def _fallback_agent_config(agent: AgentProfile, agent_id: int) -> AgentActivityConfig:
    """Heuristic config when LLM batch generation fails for an entity."""
    entity_type = (agent.source_entity_type or agent.role or "Person").lower()
    is_official = any(k in entity_type for k in ("government", "agency", "official", "university", "institution"))
    is_media = any(k in entity_type for k in ("media", "outlet", "press", "publication", "news"))
    is_individual = agent.is_individual

    if is_official:
        return AgentActivityConfig(
            agent_id=agent_id,
            entity_uuid=agent.id,
            entity_name=agent.name,
            entity_type=entity_type,
            activity_level=0.2, posts_per_hour=0.3, comments_per_hour=0.5,
            active_hours=list(range(9, 18)),
            response_delay_min=60, response_delay_max=240,
            sentiment_bias=0.0, stance="neutral", influence_weight=2.7,
        )
    if is_media:
        return AgentActivityConfig(
            agent_id=agent_id,
            entity_uuid=agent.id,
            entity_name=agent.name,
            entity_type=entity_type,
            activity_level=0.5, posts_per_hour=2.0, comments_per_hour=3.0,
            active_hours=list(range(8, 24)),
            response_delay_min=5, response_delay_max=30,
            sentiment_bias=0.0, stance="neutral", influence_weight=2.2,
        )
    if is_individual:
        return AgentActivityConfig(
            agent_id=agent_id,
            entity_uuid=agent.id,
            entity_name=agent.name,
            entity_type=entity_type,
            activity_level=0.75, posts_per_hour=1.5, comments_per_hour=4.0,
            active_hours=list(range(18, 24)) + [12, 13],
            response_delay_min=1, response_delay_max=15,
            sentiment_bias=0.0, stance=agent.stance or "neutral", influence_weight=1.0,
        )
    # Generic group / org
    return AgentActivityConfig(
        agent_id=agent_id,
        entity_uuid=agent.id,
        entity_name=agent.name,
        entity_type=entity_type,
        activity_level=0.5, posts_per_hour=1.0, comments_per_hour=2.0,
        active_hours=list(range(8, 22)),
        response_delay_min=10, response_delay_max=60,
        sentiment_bias=0.0, stance="neutral", influence_weight=1.5,
    )


# ============================================
# Step 4 — Hardcoded platform configs
# ============================================

def _build_platform_configs() -> tuple[PlatformConfig, PlatformConfig]:
    """Build the two platform recommendation algorithm configs from constants."""
    feed = PlatformConfig(
        platform="feed",
        recency_weight=0.4,
        popularity_weight=0.3,
        relevance_weight=0.3,
        viral_threshold=10,
        echo_chamber_strength=0.5,
    )
    community = PlatformConfig(
        platform="community",
        recency_weight=0.3,
        popularity_weight=0.4,
        relevance_weight=0.3,
        viral_threshold=15,
        echo_chamber_strength=0.6,
    )
    return feed, community


# ============================================
# Top-level orchestrator
# ============================================

async def generate_simulation_parameters(
    project: Project,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> SimulationParameters:
    """Generate the full SimulationParameters for a project's agent pool.

    This is the entry point for Stage 03 (Generate Config). The four sub-steps
    each have their own LLM call and their own fallback path; we never raise.
    On total failure, we still return a usable default-filled
    SimulationParameters so the pipeline can continue.
    """
    if not project.agents:
        # No agents = nothing to configure. Return defaults.
        return SimulationParameters(
            time_config=TimeSimulationConfig(),
            agent_configs=[],
            event_config=EventConfig(),
            feed_config=_build_platform_configs()[0],
            community_config=_build_platform_configs()[1],
            generation_reasoning="No agents available — defaults used.",
        )

    brief = project.brief
    constraints_str = project.constraints or ""
    signals_str = project.signals or ""
    context_parts = []
    if constraints_str:
        context_parts.append(f"CONSTRAINTS: {constraints_str}")
    if signals_str:
        context_parts.append(f"SIGNALS: {signals_str}")
    context = "\n".join(context_parts)

    num_agents = len(project.agents)
    reasoning_parts: List[str] = []

    def _report(msg: str) -> None:
        if progress_callback:
            try:
                progress_callback(msg)
            except Exception:
                pass
        logger.info(msg)

    # ===== Step 1: Time config =====
    _report(f"Step 1/4: generating time config for {num_agents} agents…")
    time_config, time_reason = await _generate_time_config(brief, context, num_agents)
    reasoning_parts.append(f"Time: {time_reason}")

    # ===== Step 2: Event config (narrative + hot topics + initial posts) =====
    _report("Step 2/4: generating narrative + hot topics + initial posts…")
    event_config, event_reason = await _generate_event_config(brief, context, project.agents)
    reasoning_parts.append(f"Event: {event_reason}")

    # ===== Step 3: Per-agent activity configs (batched) =====
    num_batches = math.ceil(num_agents / AGENTS_PER_BATCH)
    all_agent_configs: List[AgentActivityConfig] = []
    for batch_idx in range(num_batches):
        start = batch_idx * AGENTS_PER_BATCH
        end = min(start + AGENTS_PER_BATCH, num_agents)
        batch = project.agents[start:end]
        _report(f"Step 3/4: agent activity batch {batch_idx + 1}/{num_batches} ({len(batch)} agents)…")
        batch_configs = await _generate_agent_configs_batch(brief, batch, start)
        all_agent_configs.extend(batch_configs)
    reasoning_parts.append(f"Activity: {len(all_agent_configs)} per-agent configs generated")

    # ===== Step 3.5: Assign initial posts to agents =====
    _report("Step 3.5: assigning initial posts to matching agents…")
    event_config = _assign_initial_post_agents(event_config, all_agent_configs)
    assigned_count = sum(1 for p in event_config.initial_posts if p.get("poster_agent_id") is not None)
    reasoning_parts.append(f"Assigned {assigned_count} of {len(event_config.initial_posts)} initial posts to agents")

    # ===== Step 4: Hardcoded platform configs =====
    _report("Step 4/4: configuring platform recommendation algorithms…")
    feed_config, community_config = _build_platform_configs()
    reasoning_parts.append("Platforms: feed + community recommendation weights set")

    return SimulationParameters(
        time_config=time_config,
        agent_configs=all_agent_configs,
        event_config=event_config,
        feed_config=feed_config,
        community_config=community_config,
        generation_reasoning=" | ".join(reasoning_parts),
    )
