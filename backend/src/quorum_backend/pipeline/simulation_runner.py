"""
Simulation runner — round-by-round agent debate.
"""

from __future__ import annotations

import json
import logging
import random
from typing import Any, Dict, List, Optional

from quorum_backend.domains import get_domain
from quorum_backend.llm import ContentFilterError, get_llm
from quorum_backend.pipeline.llm_utils import (
    DEFAULT_AGENT_TURN_CHAR_BUDGET,
    format_transcript,
    generate_json_with_retry,
)
from quorum_backend.pipeline.models import AgentProfile, Project

logger = logging.getLogger(__name__)


AGENT_TURN_PROMPT = """This is an academic, scholarly multi-agent simulation. You are providing a research perspective for analytical purposes only.

YOUR ASSIGNED PERSPECTIVE: {name}, a {role}.

BACKGROUND:
{bio}

ANALYTICAL APPROACH:
{persona}

KNOWN BIAS TO ACKNOWLEDGE:
{bias}

INITIAL ANALYTICAL STANCE: {stance}

THE QUESTION UNDER STUDY:
{brief}

INITIAL ACTIVATION CONTEXT:
{activation_context}

CURRENT ROUND: {round_num} of {total_rounds}

PRIOR ANALYSIS FROM OTHER PERSPECTIVES:
{transcript}

It's your turn to contribute. In 2-4 sentences, provide your analytical perspective on this question. Draw on your assigned role, expertise, and acknowledged bias. Where relevant, respond to or build on the prior analysis. This is descriptive scholarship — describe how your perspective views the question, do not advocate. Conclude with a confidence score and an updated stance.

Return ONLY a JSON object:
{{
  "message": "your 2-4 sentence analytical response",
  "confidence": 0.0,
  "stance": "support" | "oppose" | "neutral"
}}
"""


CROSS_EXAMINATION_PROMPT = """This is your cross-examination turn at the end of round {round_num}.

YOUR ASSIGNED PERSPECTIVE: {name}, a {role}.

BACKGROUND:
{bio}

YOUR MANDATE: {persona}

THE DECISION UNDER REVIEW:
{brief}

WHAT WAS JUST ARGUED THIS ROUND (most recent first):
{round_transcript}

THE LEADING ARGUMENT (the position that currently has the most support):
{leading_position}

It's your turn. Your job is to ATTACK the leading argument. Do not concede. Identify the weakest assumption it depends on, the failure mode the panel hasn't named, or the alternative that was dismissed too cheaply. In 3-5 sentences, force the panel to defend the leading position explicitly rather than slide into agreement.

Return ONLY a JSON object:
{{
  "message": "your 3-5 sentence cross-examination",
  "confidence": 0.0,
  "stance": "support" | "oppose" | "neutral"
}}
"""


CONSENSUS_PROMPT = """You are a moderator summarizing a multi-agent debate.

THE BRIEF:
{brief}

THE FULL TRANSCRIPT:
{transcript}

Produce a single consensus statement that captures where the swarm landed. List the dissents — agents whose final position diverged from the majority — with their reasoning.

Return ONLY a JSON object:
{{
  "agreed_position": "1-3 sentence consensus statement",
  "agreement_rate": 0.0,
  "confidence_level": 0.0,
  "dissents": [
    {{ "agent_name": "name", "position": "their dissenting view in one sentence" }}
  ]
}}
"""


def _parse_json_object(raw: str) -> Optional[dict]:
    if not raw:
        return None
    s = raw.strip()
    if s.startswith("```"):
        s = s.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        import re

        m = re.search(r"\{[\s\S]*\}", s)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None


def _coerce_float(value, default: float = 0.5) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    return max(0.0, min(1.0, f))


def _select_active_agents(
    agents: List[AgentProfile],
    round_num: int,
    max_per_round: int = 4,
    full_panel: bool = False,
    cross_examiner_role: Optional[str] = None,
) -> List[AgentProfile]:
    if not agents:
        return []

    if full_panel:
        # Every seat speaks every round. The cross-examiner (if any) is
        # excluded here so we don't double-count it — its dedicated turn
        # runs after the round's normal turns.
        if cross_examiner_role:
            return [a for a in agents if a.role != cross_examiner_role]
        return list(agents)

    if round_num == 1:
        supporters = [a for a in agents if a.stance == "support"]
        opposers = [a for a in agents if a.stance == "oppose"]
        neutrals = [a for a in agents if a.stance == "neutral"]
        random.shuffle(supporters)
        random.shuffle(opposers)
        random.shuffle(neutrals)
        picked: List[AgentProfile] = []
        if supporters:
            picked.append(supporters[0])
        if opposers:
            picked.append(opposers[0])
        picked.extend(neutrals[: max_per_round - len(picked)])
        remaining = [a for a in agents if a not in picked]
        random.shuffle(remaining)
        picked.extend(remaining[: max(0, max_per_round - len(picked))])
        return picked[:max_per_round]

    stride = max(1, len(agents) // max_per_round)
    offset = (round_num - 1) % stride
    picked = [agents[(offset + i * stride) % len(agents)] for i in range(max_per_round)]
    return picked[:max_per_round]


def _round_messages(messages: List[Dict[str, Any]], round_num: int) -> List[Dict[str, Any]]:
    """Messages produced in a specific round, in order."""
    return [m for m in messages if m.get("round") == round_num]


def _leading_position(round_msgs: List[Dict[str, Any]]) -> str:
    """Pick the strongest argument this round to attack: the highest-confidence
    non-neutral message, falling back to the highest-confidence message overall."""
    if not round_msgs:
        return "(no arguments yet this round)"
    ranked = sorted(
        round_msgs,
        key=lambda m: (
            0 if m.get("stance") == "neutral" else 1,
            float(m.get("confidence") or 0.0),
        ),
        reverse=True,
    )
    leader = ranked[0]
    return (
        f"{leader.get('agent_name', '?')} ({leader.get('stance', '?')}, "
        f"conf={float(leader.get('confidence') or 0):.2f}): "
        f"{leader.get('content', '')}"
    )


def _format_transcript(
    messages: List[Dict[str, Any]],
    max_chars: int = DEFAULT_AGENT_TURN_CHAR_BUDGET,
) -> str:
    """Token-budgeted recent-first transcript view for an agent's turn."""
    return format_transcript(
        messages,
        max_chars=max_chars,
        recent_first=True,
        empty_text="(no messages yet — you are the first to speak)",
    )


def _build_activation_context(project: Project) -> str:
    activation = getattr(project, "activation", None)
    if not activation:
        return "(no activation plan available)"

    parts: List[str] = []
    if activation.narrative_direction:
        parts.append(f"Narrative direction: {activation.narrative_direction}")
    if activation.hot_topics:
        parts.append(f"Hot topics: {', '.join(activation.hot_topics[:6])}")
    if activation.initial_posts:
        preview = []
        for post in activation.initial_posts[:4]:
            preview.append(
                f"- {post.get('poster_type', 'Unknown')}: {str(post.get('content') or '').strip()[:180]}"
            )
        parts.append("Starter posts:\n" + "\n".join(preview))
    return "\n".join(parts) if parts else "(activation plan exists but is empty)"


def _seed_activation_messages(project: Project) -> List[Dict[str, Any]]:
    activation = getattr(project, "activation", None)
    if not activation or not activation.initial_posts:
        return []

    seeded: List[Dict[str, Any]] = []
    for idx, post in enumerate(activation.initial_posts, start=1):
        agent_name = post.get("poster_type", "Activation source")
        agent_role = "Activation"
        agent_user_name = "activation"
        stance = "neutral"

        agent_idx = post.get("poster_agent_id")
        if isinstance(agent_idx, int) and 0 <= agent_idx < len(project.agents):
            agent = project.agents[agent_idx]
            agent_name = agent.name
            agent_role = agent.role
            agent_user_name = agent.user_name
            stance = agent.stance or "neutral"

        seeded.append(
            {
                "id": f"activation_{idx}",
                "agent_id": f"activation_{idx}",
                "agent_user_name": agent_user_name,
                "agent_name": agent_name,
                "agent_role": agent_role,
                "round": 0,
                "content": str(post.get("content") or "").strip(),
                "confidence": 1.0,
                "stance": stance if stance in {"support", "oppose", "neutral"} else "neutral",
                "message_type": "activation",
            }
        )
    return [message for message in seeded if message["content"]]


async def run_simulation(project: Project, total_rounds: int = 3, agents_per_round: int = 4) -> List[Dict[str, Any]]:
    brief = project.brief
    agents = project.agents
    if not agents:
        return []

    messages: List[Dict[str, Any]] = _seed_activation_messages(project)
    project.debate_messages = messages
    if messages:
        project.log("info", f"Activation seeded {len(messages)} starter message(s)", stage="simulating")

    llm = get_llm()
    activation_context = _build_activation_context(project)

    # Domain shape: whether every seat must speak each round, and whether a
    # specific role gets a dedicated cross-examination turn at the round's end.
    domain = get_domain(getattr(project, "domain", "general"))
    full_panel = bool(getattr(domain, "full_panel_per_round", False))
    cross_examiner_role = getattr(domain, "cross_examiner_role", None) or None
    cross_examiner = (
        next((a for a in agents if a.role == cross_examiner_role), None)
        if cross_examiner_role
        else None
    )
    if full_panel:
        project.log(
            "info",
            f"Domain {domain.key}: full {len(agents)}-seat panel speaks every round",
            stage="simulating",
        )
    if cross_examiner is not None:
        project.log(
            "info",
            f"Domain {domain.key}: {cross_examiner.name} runs a cross-examination at end of each round",
            stage="simulating",
        )

    for round_num in range(1, total_rounds + 1):
        active = _select_active_agents(
            agents,
            round_num,
            max_per_round=agents_per_round,
            full_panel=full_panel,
            cross_examiner_role=cross_examiner_role,
        )
        project.log("info", f"Round {round_num}/{total_rounds}: {len(active)} agents speaking", stage="simulating")

        for agent in active:
            transcript = _format_transcript(messages)
            user_msg = AGENT_TURN_PROMPT.format(
                name=agent.name,
                role=agent.role,
                bio=agent.bio,
                persona=agent.persona,
                bias=agent.bias or "(none stated)",
                stance=agent.stance,
                brief=brief,
                activation_context=activation_context,
                round_num=round_num,
                total_rounds=total_rounds,
                transcript=transcript,
            )

            try:
                parsed = await generate_json_with_retry(
                    llm,
                    system=(
                        "You are a debate participant in an academic, scholarly multi-agent simulation. "
                        "You analyze the brief from your assigned perspective for research purposes. "
                        "Stay in character. Return only the JSON object."
                    ),
                    user_message=user_msg,
                    stage="simulate",
                    parser=_parse_json_object,
                    max_tokens=900,
                )
            except ContentFilterError:
                project.log("warn", f"{agent.name} skipped (content filter blocked the prompt)", stage="simulating")
                continue
            except Exception as exc:
                logger.warning("Agent turn LLM call failed for %s: %s", agent.name, exc)
                project.log("warn", f"{agent.name} skipped (LLM error)", stage="simulating")
                continue

            if not parsed:
                project.log("warn", f"{agent.name} skipped (no parseable response)", stage="simulating")
                continue

            content = str(parsed.get("message") or "").strip()
            if not content:
                continue

            stance = str(parsed.get("stance") or agent.stance).lower()
            if stance not in {"support", "oppose", "neutral"}:
                stance = "neutral"

            message = {
                "id": f"msg_{round_num}_{len(messages) + 1}",
                "agent_id": agent.id,
                "agent_user_name": agent.user_name,
                "agent_name": agent.name,
                "agent_role": agent.role,
                "round": round_num,
                "content": content,
                "confidence": _coerce_float(parsed.get("confidence"), 0.7),
                "stance": stance,
            }
            messages.append(message)
            project.log("info", f"{agent.name} spoke ({stance}, conf={message['confidence']:.2f})", stage="simulating")

        # End-of-round cross-examination by the designated role, when set.
        if cross_examiner is not None:
            round_msgs = _round_messages(messages, round_num)
            if not round_msgs:
                project.log(
                    "info",
                    f"Skipping cross-examination for round {round_num}: no turns to attack",
                    stage="simulating",
                )
                continue
            cx_msg = await _run_cross_examination_turn(
                project=project,
                llm=llm,
                cross_examiner=cross_examiner,
                brief=brief,
                round_num=round_num,
                round_msgs=round_msgs,
                messages=messages,
            )
            if cx_msg is not None:
                messages.append(cx_msg)

    return messages


async def _run_cross_examination_turn(
    *,
    project: Project,
    llm,
    cross_examiner: AgentProfile,
    brief: str,
    round_num: int,
    round_msgs: List[Dict[str, Any]],
    messages: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """One extra turn for the cross-examiner, prompted to attack the round's
    leading argument. Failures are logged and skipped, never fatal."""
    leading = _leading_position(round_msgs)
    round_transcript = format_transcript(
        round_msgs,
        max_chars=DEFAULT_AGENT_TURN_CHAR_BUDGET,
        recent_first=True,
        empty_text="(no turns this round)",
    )
    user_msg = CROSS_EXAMINATION_PROMPT.format(
        name=cross_examiner.name,
        role=cross_examiner.role,
        bio=cross_examiner.bio,
        persona=cross_examiner.persona,
        brief=brief,
        round_num=round_num,
        round_transcript=round_transcript,
        leading_position=leading,
    )
    try:
        parsed = await generate_json_with_retry(
            llm,
            system=(
                "You are the panel's designated skeptic, running a cross-"
                "examination turn. Your job is to attack the leading "
                "argument — do not concede. Return only the JSON object."
            ),
            user_message=user_msg,
            stage="simulate",
            parser=_parse_json_object,
            max_tokens=900,
        )
    except ContentFilterError:
        project.log(
            "warn",
            f"{cross_examiner.name} cross-examination skipped (content filter)",
            stage="simulating",
        )
        return None
    except Exception as exc:
        logger.warning("Cross-examination LLM call failed for %s: %s", cross_examiner.name, exc)
        project.log(
            "warn",
            f"{cross_examiner.name} cross-examination skipped (LLM error)",
            stage="simulating",
        )
        return None

    if not parsed:
        return None
    content = str(parsed.get("message") or "").strip()
    if not content:
        return None
    stance = str(parsed.get("stance") or "oppose").lower()
    if stance not in {"support", "oppose", "neutral"}:
        stance = "oppose"
    cx_msg = {
        "id": f"msg_{round_num}_cx_{len(messages) + 1}",
        "agent_id": cross_examiner.id,
        "agent_user_name": cross_examiner.user_name,
        "agent_name": cross_examiner.name,
        "agent_role": cross_examiner.role,
        "round": round_num,
        "content": content,
        "confidence": _coerce_float(parsed.get("confidence"), 0.7),
        "stance": stance,
        "message_type": "cross_examination",
    }
    project.log(
        "info",
        f"{cross_examiner.name} cross-examined round {round_num} ({stance}, conf={cx_msg['confidence']:.2f})",
        stage="simulating",
    )
    return cx_msg


def _tally_final_stances(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute the actual vote distribution from each agent's most recent
    message. Returns counts, the plurality stance, and the agreement rate
    (plurality / total) — an objective, vote-derived signal that complements
    the LLM moderator's vibe-based summary."""
    if not messages:
        return {
            "counts": {"support": 0, "oppose": 0, "neutral": 0},
            "plurality": "neutral",
            "agreement_rate": 0.0,
            "voters": 0,
        }
    final_by_agent: Dict[str, str] = {}
    for m in messages:
        if m.get("message_type") == "activation":
            continue
        agent_id = m.get("agent_id")
        if not agent_id:
            continue
        stance = (m.get("stance") or "neutral").lower()
        if stance not in {"support", "oppose", "neutral"}:
            stance = "neutral"
        final_by_agent[agent_id] = stance  # latest wins
    counts = {"support": 0, "oppose": 0, "neutral": 0}
    for s in final_by_agent.values():
        counts[s] += 1
    voters = sum(counts.values()) or 1
    plurality = max(counts, key=counts.get)
    return {
        "counts": counts,
        "plurality": plurality,
        "agreement_rate": round(counts[plurality] / voters, 3),
        "voters": sum(counts.values()),
    }


def _voter_dissents(
    messages: List[Dict[str, Any]],
    plurality: str,
) -> List[Dict[str, str]]:
    """Agents whose final stance differs from the plurality, with their
    last message as the dissent text."""
    if plurality not in {"support", "oppose", "neutral"}:
        return []
    final_by_agent: Dict[str, Dict[str, Any]] = {}
    for m in messages:
        if m.get("message_type") == "activation":
            continue
        agent_id = m.get("agent_id")
        if not agent_id:
            continue
        final_by_agent[agent_id] = m  # latest wins
    out: List[Dict[str, str]] = []
    for m in final_by_agent.values():
        stance = (m.get("stance") or "neutral").lower()
        if stance != plurality:
            out.append(
                {
                    "agent_name": str(m.get("agent_name") or "").strip(),
                    "position": str(m.get("content") or "").strip()[:280],
                }
            )
    return out


async def generate_consensus(project: Project) -> Optional[Dict[str, Any]]:
    if not project.debate_messages:
        return None

    transcript_lines = [
        f"[R{m.get('round', '?')}] {m.get('agent_name', '?')} ({m.get('stance', '?')}): {m.get('content', '')}"
        for m in project.debate_messages
    ]
    transcript = "\n".join(transcript_lines)

    prompt = CONSENSUS_PROMPT.format(brief=project.brief, transcript=transcript)

    llm = get_llm()
    try:
        parsed = await generate_json_with_retry(
            llm,
            system="You are a neutral moderator. Return only the JSON object.",
            user_message=prompt,
            stage="simulate",
            parser=_parse_json_object,
            max_tokens=900,
        )
    except Exception as exc:
        logger.warning("Consensus LLM call failed: %s", exc)
        return None

    # Vote-derived signals from the agents' final stances. These override
    # the moderator's vibe-based agreement_rate / dissent list with an
    # objectively computed plurality + dissenters.
    tally = _tally_final_stances(project.debate_messages)
    voter_dissents = _voter_dissents(project.debate_messages, tally["plurality"])

    if not parsed:
        # Even if the LLM moderator failed, ship the vote-derived signals
        # so the consumer still has something deterministic to display.
        consensus = {
            "agreed_position": "(moderator summary unavailable; see vote tally)",
            "agreement_rate": tally["agreement_rate"],
            "confidence_level": 0.0,
            "dissents": voter_dissents,
            "vote_tally": tally,
        }
        project.consensus = consensus
        return consensus

    consensus = {
        "agreed_position": str(parsed.get("agreed_position") or "").strip(),
        # Trust the vote count over the LLM's self-reported number.
        "agreement_rate": tally["agreement_rate"],
        "confidence_level": _coerce_float(parsed.get("confidence_level"), 0.75),
        # Prefer vote-derived dissents (objective). Fall back to the
        # moderator's list only if no voters disagreed with the plurality.
        "dissents": voter_dissents
        or [
            {
                "agent_name": str(d.get("agent_name") or "").strip(),
                "position": str(d.get("position") or "").strip(),
            }
            for d in (parsed.get("dissents") or [])
            if isinstance(d, dict)
        ],
        "vote_tally": tally,
    }
    project.consensus = consensus
    return consensus


async def chat_with_agent(project: Project, agent: AgentProfile, user_message: str) -> Optional[str]:
    transcript_summary = _format_transcript(project.debate_messages)
    consensus_str = ""
    if project.consensus:
        consensus_str = (
            f"FINAL CONSENSUS: {project.consensus.get('agreed_position', '')}\n"
            f"AGREEMENT RATE: {project.consensus.get('agreement_rate', 0):.0%}"
        )
    activation_str = _build_activation_context(project)

    system = (
        f"You are {agent.name}, a {agent.role}. Stay completely in character. "
        f"You just participated in a debate about: {project.brief}\n\n"
        f"YOUR BIO: {agent.bio}\n"
        f"YOUR PERSONA: {agent.persona}\n"
        f"YOUR BIAS: {agent.bias or '(none stated)'}\n\n"
        f"INITIAL ACTIVATION CONTEXT:\n{activation_str}\n\n"
        f"WHAT WAS DISCUSSED:\n{transcript_summary}\n\n"
        f"{consensus_str}\n\n"
        "Answer the user's follow-up question in 2-4 sentences. Speak in your voice. Do not break character."
    )

    try:
        llm = get_llm()
        raw = await llm.generate(
            system=system,
            user_message=user_message,
            max_tokens=400,
            stage="chat",
        )
    except Exception as exc:
        logger.warning("Deep interaction LLM call failed: %s", exc)
        return None

    return (raw or "").strip()

